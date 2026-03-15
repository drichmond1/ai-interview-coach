"""
Core interview state machine.

Coordinates prompts.py and llm_client.py to manage a full interview session.
"""

import json
import re
from dataclasses import dataclass, field

from llm_client import chat
from prompts import (
    INTERVIEWER_SYSTEM_PROMPT,
    analyze_jd_prompt,
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


def start_interview(jd: str, provider: str, api_key: str) -> tuple["InterviewState", str]:
    """
    Initialise a new interview session.

    Analyses the job description, creates an InterviewState, and returns the
    state along with the first interview question.
    """
    try:
        raw = chat(_build_messages(analyze_jd_prompt(jd)), provider, api_key, temperature=0.2)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to analyse the job description via {provider}. "
            "Check your API key and try again."
        ) from exc

    # Strip accidental markdown code fences the model may add despite instructions.
    cleaned = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        role_info = json.loads(cleaned)
    except json.JSONDecodeError:
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
        phase="interviewing",
        current_index=0,
    )

    first_question = _generate_next_question(state)
    return state, first_question


def _generate_next_question(state: InterviewState) -> str:
    """Ask the LLM for the next interview question, update state, and return it."""
    question_number = len(state.questions) + 1
    total = state.role_info.get("num_questions", 8)

    try:
        question_text = chat(
            _build_messages(
                generate_question_prompt(
                    state.jd,
                    state.role_info,
                    question_number,
                    total,
                    state.conversation_history,
                )
            ),
            state.provider,
            state.api_key,
            temperature=0.7,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to generate question {question_number} via {state.provider}. "
            "Check your API key and try again."
        ) from exc

    question_text = question_text.strip()
    state.questions.append(question_text)
    state.conversation_history.append({"role": "assistant", "content": question_text})
    return question_text


def submit_answer(
    state: InterviewState, answer: str
) -> tuple["InterviewState", str, str]:
    """
    Record the candidate's answer, generate feedback, and advance the session.

    Returns:
        (state, feedback_text, next_question_or_summary)
        When state.phase == "done", the third element is the final summary.
        Otherwise it is the next interview question.
    """
    state.answers.append(answer)
    state.conversation_history.append({"role": "user", "content": answer})

    question_number = state.current_index + 1
    total = state.role_info.get("num_questions", 8)
    current_question = state.questions[state.current_index]

    try:
        feedback_text = chat(
            _build_messages(
                generate_feedback_prompt(current_question, answer, question_number, total)
            ),
            state.provider,
            state.api_key,
            temperature=0.3,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to generate feedback for question {question_number} via {state.provider}. "
            "Check your API key and try again."
        ) from exc

    feedback_text = feedback_text.strip()
    state.feedbacks.append(feedback_text)
    state.scores.append(_extract_score(feedback_text))
    state.current_index += 1

    if state.current_index >= total:
        state.phase = "done"
        summary = get_summary(state)
        return state, feedback_text, summary

    next_question = _generate_next_question(state)
    return state, feedback_text, next_question


def get_summary(state: InterviewState) -> str:
    """Generate and return the final interview summary report."""
    qa_pairs = [
        {"question": q, "answer": a, "feedback": f, "score": s}
        for q, a, f, s in zip(state.questions, state.answers, state.feedbacks, state.scores)
    ]

    try:
        summary_text = chat(
            _build_messages(generate_summary_prompt(state.jd, state.role_info, qa_pairs)),
            state.provider,
            state.api_key,
            temperature=0.3,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to generate interview summary via {state.provider}. "
            "Check your API key and try again."
        ) from exc

    return summary_text.strip()


def get_progress(state: InterviewState) -> tuple[int, int]:
    """Return (questions_asked_so_far, total_questions)."""
    return len(state.questions), state.role_info.get("num_questions", 8)
