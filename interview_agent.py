"""
Core interview state machine.

Coordinates prompts.py and llm_client.py to manage a full interview session.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from llm_client import chat
from prompts import (
    INTERVIEWER_SYSTEM_PROMPT,
    analyze_jd_prompt,
    classify_response_prompt,
    clarifying_question_prompt,
    generate_feedback_prompt,
    generate_question_prompt,
    generate_summary_prompt,
)

_SCORE_RE = re.compile(r"\*{0,2}Score\*{0,2}:\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*5", re.IGNORECASE)

_DEFAULT_ROLE_INFO = {
    "role_title": "Software Engineer",
    "seniority": "mid",
    "domain": "software engineering",
    "key_skills": [],
    "num_questions": 8,
    "question_breakdown": {"intro": 1, "technical": 5, "behavioral": 2},
}


@dataclass
class InterviewState:
    jd: str
    provider: str
    api_key: str
    role_info: dict
    resume: str = ""
    difficulty: str = "medium"
    questions: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    feedbacks: list[str] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)
    phase: str = "setup"
    current_index: int = 0


def _build_messages(user_prompt: str) -> list[dict]:
    return [
        {"role": "system", "content": INTERVIEWER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _extract_score(feedback_text: str) -> float:
    match = _SCORE_RE.search(feedback_text)
    if match:
        return float(match.group(1))
    return 3.0


def start_interview(jd: str, provider: str, api_key: str, resume: str = "", difficulty: str = "medium") -> tuple["InterviewState", str]:
    """
    Initialise a new interview session.

    Analyses the job description, creates an InterviewState, and returns the
    state along with the first interview question.
    """
    try:
        raw = chat(_build_messages(analyze_jd_prompt(jd)), provider, api_key, temperature=0.2)
    except Exception as exc:
        logger.error("JD analysis failed: provider=%s error=%s", provider, exc)
        raise RuntimeError(
            f"Failed to analyse the job description via {provider}: {exc}"
        ) from exc

    # Strip accidental markdown code fences the model may add despite instructions.
    cleaned = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        role_info = json.loads(cleaned)
        logger.info("JD analysis parsed successfully: role=%s seniority=%s",
                     role_info.get("role_title"), role_info.get("seniority"))
    except json.JSONDecodeError:
        logger.warning("JD analysis returned invalid JSON, using defaults. Raw response: %.200s", cleaned)
        role_info = dict(_DEFAULT_ROLE_INFO)

    # Ensure required keys exist with sensible fallbacks.
    role_info.setdefault("role_title", _DEFAULT_ROLE_INFO["role_title"])
    role_info.setdefault("seniority", _DEFAULT_ROLE_INFO["seniority"])
    role_info.setdefault("domain", _DEFAULT_ROLE_INFO["domain"])
    role_info.setdefault("key_skills", [])
    role_info.setdefault("num_questions", _DEFAULT_ROLE_INFO["num_questions"])
    role_info.setdefault("question_breakdown", dict(_DEFAULT_ROLE_INFO["question_breakdown"]))

    state = InterviewState(
        jd=jd,
        provider=provider,
        api_key=api_key,
        role_info=role_info,
        resume=resume,
        difficulty=difficulty,
        phase="interviewing",
        current_index=0,
    )

    logger.info("Interview started: provider=%s role=%s difficulty=%s resume_provided=%s",
                provider, role_info.get("role_title"), difficulty, bool(resume))

    first_question = _generate_next_question(state)
    return state, first_question


def _generate_next_question(state: InterviewState) -> str:
    """Ask the LLM for the next interview question, update state, and return it."""
    question_number = len(state.questions) + 1
    logger.info("Generating question %d", question_number)

    try:
        question_text = chat(
            _build_messages(
                generate_question_prompt(
                    state.jd,
                    state.role_info,
                    question_number,
                    state.conversation_history,
                    state.difficulty,
                )
            ),
            state.provider,
            state.api_key,
            temperature=0.9,
        )
    except Exception as exc:
        logger.error("Question generation failed: question_number=%d error=%s", question_number, exc)
        raise RuntimeError(
            f"Failed to generate question {question_number} via {state.provider}. "
            "Check your API key and try again."
        ) from exc

    question_text = question_text.strip()
    state.questions.append(question_text)
    state.conversation_history.append({"role": "assistant", "content": question_text})
    logger.info("Question %d generated, length=%d chars", question_number, len(question_text))
    return question_text


def _classify_response(state: InterviewState, response_text: str) -> str:
    """Classify a candidate's response as 'clarifying' or 'answer'."""
    current_question = state.questions[state.current_index]
    try:
        result = chat(
            _build_messages(classify_response_prompt(current_question, response_text)),
            state.provider,
            state.api_key,
            temperature=0.1,
        )
    except Exception:
        return "answer"
    return "clarifying" if "CLARIFYING" in result.strip().upper() else "answer"


def ask_clarification(state: InterviewState, question_text: str) -> tuple["InterviewState", str]:
    """
    Handle a candidate's clarifying question about the current interview question.

    Returns:
        (state, interviewer_response)
    """
    current_question = state.questions[state.current_index]
    state.conversation_history.append({"role": "user", "content": question_text})
    logger.info("Handling clarifying question for question_index=%d", state.current_index)

    try:
        response = chat(
            _build_messages(
                clarifying_question_prompt(
                    current_question,
                    question_text,
                    state.conversation_history,
                )
            ),
            state.provider,
            state.api_key,
            temperature=0.9,
        )
    except Exception as exc:
        logger.error("Clarification response failed: %s", exc)
        raise RuntimeError(
            f"Failed to respond to clarifying question via {state.provider}. "
            "Check your API key and try again."
        ) from exc

    response = response.strip()
    state.conversation_history.append({"role": "assistant", "content": response})
    logger.info("Clarification response generated, length=%d chars", len(response))
    return state, response


def handle_response(
    state: InterviewState, response_text: str
) -> tuple["InterviewState", str, str | None, str | None]:
    """
    Process a candidate's response — auto-detecting whether it is a clarifying
    question or an actual answer.

    Returns:
        (state, response_type, interviewer_reply, feedback_and_next)
        - If clarifying: response_type="clarifying", interviewer_reply=str, feedback_and_next=None
        - If answer: response_type="answer", interviewer_reply=None,
          feedback_and_next is a (feedback, next_question) tuple packed as two values
    """
    classification = _classify_response(state, response_text)

    if classification == "clarifying":
        new_state, reply = ask_clarification(state, response_text)
        return new_state, "clarifying", reply, None

    new_state, feedback, next_q = submit_answer(state, response_text)
    return new_state, "answer", feedback, next_q


def submit_answer(
    state: InterviewState, answer: str
) -> tuple["InterviewState", str, str]:
    """
    Record the candidate's answer, generate feedback, and advance the session.

    Returns:
        (state, feedback_text, next_question)
    """
    state.answers.append(answer)
    state.conversation_history.append({"role": "user", "content": answer})

    question_number = state.current_index + 1
    current_question = state.questions[state.current_index]
    logger.info("Evaluating answer for question %d, answer_length=%d chars", question_number, len(answer))

    try:
        feedback_text = chat(
            _build_messages(
                generate_feedback_prompt(current_question, answer, question_number, state.resume, state.difficulty)
            ),
            state.provider,
            state.api_key,
            temperature=0.5,
        )
    except Exception as exc:
        logger.error("Feedback generation failed: question_number=%d error=%s", question_number, exc)
        raise RuntimeError(
            f"Failed to generate feedback for question {question_number} via {state.provider}. "
            "Check your API key and try again."
        ) from exc

    feedback_text = feedback_text.strip()
    state.feedbacks.append(feedback_text)
    score = _extract_score(feedback_text)
    state.scores.append(score)
    state.current_index += 1
    logger.info("Answer evaluated: question=%d score=%.1f/5", question_number, score)

    next_question = _generate_next_question(state)
    return state, feedback_text, next_question


def get_summary(state: InterviewState) -> str:
    """Generate and return the final interview summary report."""
    qa_pairs = [
        {"question": q, "answer": a, "feedback": f, "score": s}
        for q, a, f, s in zip(state.questions, state.answers, state.feedbacks, state.scores)
    ]
    avg_score = sum(state.scores) / len(state.scores) if state.scores else 0
    logger.info("Generating interview summary: questions_answered=%d avg_score=%.1f/5",
                len(qa_pairs), avg_score)

    try:
        summary_text = chat(
            _build_messages(generate_summary_prompt(state.jd, state.role_info, qa_pairs, state.resume)),
            state.provider,
            state.api_key,
            temperature=0.5,
        )
    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        raise RuntimeError(
            f"Failed to generate interview summary via {state.provider}. "
            "Check your API key and try again."
        ) from exc

    logger.info("Interview summary generated, length=%d chars", len(summary_text.strip()))
    return summary_text.strip()


def get_progress(state: InterviewState) -> int:
    """Return the number of questions asked so far."""
    return len(state.questions)
