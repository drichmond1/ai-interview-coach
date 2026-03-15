"""
Prompt templates for the AI interview coach.
"""

INTERVIEWER_SYSTEM_PROMPT = (
    "You are a professional technical interviewer conducting a structured job interview. "
    "Your style is direct, encouraging, and grounded — you ask focused, clear questions "
    "appropriate to the role and seniority level. You are supportive without being "
    "sycophantic, and constructively critical without being harsh. "
    "You rely strictly on the job description and the candidate's responses; "
    "you never fabricate facts, invent requirements, or make assumptions beyond what "
    "is explicitly stated. Your goal is to give the candidate a fair, realistic interview "
    "experience that helps them grow."
)


def analyze_jd_prompt(jd: str) -> str:
    """Return a prompt that asks the LLM to analyze a job description and output JSON."""
    return (
        "Analyze the following job description and return a JSON object with these fields:\n\n"
        "- role_title (string): the job title as written in the description\n"
        "- seniority (string): one of 'junior', 'mid', 'senior', 'staff', or 'lead'\n"
        "- domain (string): the primary engineering/technical domain (e.g. 'backend engineering')\n"
        "- key_skills (array of strings): the most important technical skills mentioned\n"
        "- num_questions (integer): total interview questions to ask, based on seniority:\n"
        "    junior → 6–8, mid → 8–10, senior/staff/lead → 10–12\n"
        "- question_breakdown (object): how to distribute questions across categories:\n"
        "    { \"intro\": <int>, \"technical\": <int>, \"behavioral\": <int> }\n"
        "  The three values must sum to num_questions. "
        "  Use roughly 1 intro, ~70% technical, ~20-25% behavioral.\n\n"
        "Rules:\n"
        "- Respond with ONLY valid JSON. No markdown, no code fences, no commentary.\n"
        "- The response must be directly parseable by json.loads().\n\n"
        "Example output shape (values are illustrative):\n"
        '{\n'
        '  "role_title": "Senior Software Engineer",\n'
        '  "seniority": "senior",\n'
        '  "domain": "backend engineering",\n'
        '  "key_skills": ["Python", "REST APIs", "PostgreSQL"],\n'
        '  "num_questions": 10,\n'
        '  "question_breakdown": {\n'
        '    "intro": 1,\n'
        '    "technical": 7,\n'
        '    "behavioral": 2\n'
        '  }\n'
        '}\n\n'
        f"Job Description:\n{jd}"
    )


def generate_question_prompt(
    jd: str,
    role_info: dict,
    question_number: int,
    conversation_history: list[dict],
    difficulty: str = "medium",
) -> str:
    """
    Return a prompt that asks the LLM to generate the next interview question.

    Args:
        jd: The full job description text.
        role_info: Parsed role metadata from analyze_jd_prompt (role_title, seniority, etc.).
        question_number: 1-based index of the question about to be asked.
        conversation_history: List of {role, content} dicts representing prior exchanges.
        difficulty: One of 'easy', 'medium', 'hard'.
    """
    breakdown = role_info.get("question_breakdown", {})
    intro_count = breakdown.get("intro", 1)
    technical_count = breakdown.get("technical", 0)
    behavioral_count = breakdown.get("behavioral", 0)
    intro_end = intro_count
    technical_end = intro_count + technical_count
    planned_total = intro_count + technical_count + behavioral_count

    if question_number <= intro_end:
        phase = "introductory/warm-up"
        phase_guidance = (
            "Ask a friendly opening question such as a brief self-introduction or "
            "background summary. Keep it welcoming and low-pressure."
        )
    elif question_number <= technical_end:
        phase = "core technical"
        phase_guidance = (
            "Ask a substantive technical question directly relevant to the role's key skills "
            "and the job description. Vary depth and topic from previous questions."
        )
    elif question_number <= planned_total:
        phase = "behavioral"
        phase_guidance = (
            "Ask a behavioral question using a situational framing (e.g., 'Tell me about a "
            "time when…' or 'How have you handled…'). Focus on teamwork, communication, "
            "or problem-solving as relevant to the role."
        )
    else:
        phase = "extended"
        phase_guidance = (
            "Continue the interview with a mix of technical and behavioral questions. "
            "Vary the topic and depth from previous questions. Draw on the job description "
            "for relevant areas not yet covered."
        )

    history_text = ""
    if conversation_history:
        lines = []
        for turn in conversation_history:
            label = "Interviewer" if turn["role"] == "assistant" else "Candidate"
            lines.append(f"{label}: {turn['content']}")
        history_text = "\n\nConversation so far:\n" + "\n\n".join(lines)

    difficulty_guidance = {
        "easy": (
            "Difficulty: Easy — Ask straightforward, foundational questions. "
            "Focus on basic concepts, definitions, and simple scenarios. "
            "Avoid multi-part questions or deep system design."
        ),
        "medium": (
            "Difficulty: Medium — Ask moderately challenging questions that test "
            "practical experience and solid understanding. Include some follow-up "
            "depth but keep questions focused."
        ),
        "hard": (
            "Difficulty: Hard — Ask challenging, in-depth questions that test expert-level "
            "knowledge. Include complex scenarios, system design trade-offs, edge cases, "
            "and multi-layered problems. Expect detailed, nuanced answers."
        ),
    }
    diff_text = difficulty_guidance.get(difficulty, difficulty_guidance["medium"])

    return (
        f"You are interviewing a candidate for the role: {role_info.get('role_title', 'the position')} "
        f"({role_info.get('seniority', 'unknown')} level, {role_info.get('domain', 'technical')}).\n\n"
        f"This is question {question_number}. "
        f"Phase: {phase}.\n"
        f"{diff_text}\n"
        f"Guidance: {phase_guidance}\n\n"
        f"Job Description:\n{jd}"
        f"{history_text}\n\n"
        "Instructions:\n"
        "- Output ONLY the question text. No preamble, no labels, no 'Sure! Here's question N:' intro.\n"
        "- The question must be concise, specific, and directly relevant to the job description.\n"
        "- Do not repeat a topic already covered in the conversation above.\n"
        "- Do not add any follow-up commentary after the question."
    )


def classify_response_prompt(
    question: str,
    candidate_response: str,
) -> str:
    """
    Return a prompt that asks the LLM to classify whether the candidate's
    response is a clarifying question or an actual answer.
    """
    return (
        "You are classifying a candidate's response during a technical interview.\n\n"
        f"Interview question: {question}\n\n"
        f"Candidate's response: {candidate_response}\n\n"
        "Is the candidate asking a clarifying question about the interview question, "
        "or are they providing their actual answer?\n\n"
        "Rules:\n"
        "- If the response is asking for more information, clarification, or context "
        "about the question, classify it as CLARIFYING.\n"
        "- If the response is attempting to answer the question (even partially or "
        "poorly), classify it as ANSWER.\n"
        "- Respond with ONLY one word: either CLARIFYING or ANSWER. Nothing else."
    )


def clarifying_question_prompt(
    question: str,
    clarifying_question: str,
    conversation_history: list[dict],
) -> str:
    """
    Return a prompt for the interviewer to respond to a candidate's clarifying question.

    The interviewer should answer helpfully without giving away the answer.
    """
    history_text = ""
    if conversation_history:
        lines = []
        for turn in conversation_history:
            label = "Interviewer" if turn["role"] == "assistant" else "Candidate"
            lines.append(f"{label}: {turn['content']}")
        history_text = "\n\nConversation so far:\n" + "\n\n".join(lines)

    return (
        "You are a professional technical interviewer. The candidate has asked a "
        "clarifying question about your most recent interview question.\n\n"
        f"Your interview question was: {question}\n\n"
        f"Candidate's clarifying question: {clarifying_question}\n"
        f"{history_text}\n\n"
        "Instructions:\n"
        "- Answer the clarifying question helpfully and concisely.\n"
        "- Provide enough context for the candidate to answer well, but do NOT "
        "give away the answer itself.\n"
        "- Stay in character as the interviewer.\n"
        "- Output ONLY your response. No labels or preamble."
    )


def generate_feedback_prompt(
    question: str,
    answer: str,
    question_number: int,
    resume: str = "",
    difficulty: str = "medium",
) -> str:
    """
    Return a prompt asking the LLM to evaluate a candidate's answer.

    Args:
        question: The interview question that was asked.
        answer: The candidate's response.
        question_number: 1-based position of this question.
        resume: Optional candidate resume text for context.
        difficulty: Interview difficulty level ('easy', 'medium', 'hard').
    """
    resume_section = ""
    if resume.strip():
        resume_section = (
            f"\n\nCandidate's Resume (use this for additional context when evaluating):\n{resume}\n"
        )

    difficulty_expectation = {
        "easy": "The interview is set to Easy difficulty — evaluate leniently, focusing on whether core concepts are understood.",
        "medium": "The interview is set to Medium difficulty — expect solid practical knowledge and clear explanations.",
        "hard": "The interview is set to Hard difficulty — expect expert-level depth, nuance, and thorough coverage of edge cases.",
    }
    diff_text = difficulty_expectation.get(difficulty, difficulty_expectation["medium"])

    return (
        f"You are evaluating a candidate's answer to question {question_number} "
        "in a technical interview.\n\n"
        f"{diff_text}\n\n"
        f"Question: {question}\n\n"
        f"Candidate's Answer: {answer}\n"
        f"{resume_section}\n"
        "Provide concise, specific feedback on this answer. "
        "Keep the total response to 3–6 sentences across all sections. "
        "Be constructive and concrete — reference what the candidate actually said.\n\n"
        "Format your response as structured markdown with exactly these four sections:\n\n"
        "**Strengths**\n"
        "- bullet points of what was good about the answer\n\n"
        "**Areas to Improve**\n"
        "- bullet points of what could be stronger or was missing\n\n"
        "**Score**: X/5 — one-line justification\n\n"
        "**Example Strong Answer**\n"
        "Write a concise example of how a strong candidate would answer this specific question, "
        "addressing the gaps identified above. Keep it to 3–5 sentences.\n\n"
        "Scoring guide:\n"
        "  5 – Excellent: thorough, accurate, well-structured\n"
        "  4 – Good: solid answer with minor gaps\n"
        "  3 – Adequate: covers the basics but lacks depth\n"
        "  2 – Weak: significant gaps or inaccuracies\n"
        "  1 – Poor: largely incorrect or off-topic\n\n"
        "Do not add any text before or after the four markdown sections."
    )


def generate_summary_prompt(
    jd: str,
    role_info: dict,
    qa_pairs: list[dict],
    resume: str = "",
) -> str:
    """
    Return a prompt for generating a final interview summary report.

    Args:
        jd: The full job description text.
        role_info: Parsed role metadata (role_title, seniority, domain, key_skills, etc.).
        qa_pairs: List of dicts with keys: question, answer, feedback, score.
        resume: Optional candidate resume text for context.
    """
    qa_text_lines = []
    for i, qa in enumerate(qa_pairs, start=1):
        qa_text_lines.append(
            f"Q{i}: {qa['question']}\n"
            f"Answer: {qa['answer']}\n"
            f"Feedback: {qa['feedback']}\n"
            f"Score: {qa.get('score', 'N/A')}/5"
        )
    qa_text = "\n\n".join(qa_text_lines)

    role_title = role_info.get("role_title", "the role")
    seniority = role_info.get("seniority", "")
    domain = role_info.get("domain", "")

    resume_section = ""
    if resume.strip():
        resume_section = f"\nCandidate's Resume:\n{resume}\n"

    return (
        f"You have just completed a mock interview for the role: {role_title} "
        f"({seniority}, {domain}).\n\n"
        f"Job Description:\n{jd}\n"
        f"{resume_section}\n"
        f"Interview Q&A with per-question feedback and scores:\n\n{qa_text}\n\n"
        "Generate a final interview summary report. "
        "Compute the Overall Score as the average of the per-question scores, rounded to one decimal place. "
        "Base all observations strictly on the candidate's actual answers above.\n\n"
        "Format your response as structured markdown with exactly these five sections:\n\n"
        "**Overall Score**: X.X/5\n\n"
        f"**Role**: {role_title}\n\n"
        "**Top Strengths**\n"
        "- (3 bullet points highlighting the candidate's strongest demonstrated skills/qualities)\n\n"
        "**Key Development Areas**\n"
        "- (3 bullet points identifying the most important areas for improvement)\n\n"
        "**Recommendation**: Hire / Consider / Pass — brief one-to-two sentence justification\n\n"
        "Recommendation guide:\n"
        "  Hire     – Overall score ≥ 4.0 and no critical gaps\n"
        "  Consider – Overall score 2.5–3.9 or notable strengths offset by gaps\n"
        "  Pass     – Overall score < 2.5 or significant skill misalignment\n\n"
        "Do not add any text before or after the five markdown sections."
    )
