"""Generate topic-specific practice papers without changing study progress."""

import json
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import ChatOllama
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.config import settings
from backend.models import CurriculumItem, LearningHistory, Newsletter


class Question(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, description="Complete question, including any choices")
    answer: str = Field(min_length=1, description="Correct answer or a sample acceptable answer")
    topic: str | None = Field(default=None, description="Exact selected topic tested by this question")


class PaperContent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1)
    instructions: str = Field(min_length=1, description="Short instructions for the child")
    questions: list[Question] = Field(min_length=1, max_length=20)


class PracticePaper(PaperContent):
    subject: str
    topics: list[str] = Field(min_length=1, max_length=20)
    grade: str
    difficulty: str
    duration_minutes: int

    @model_validator(mode="before")
    @classmethod
    def accept_older_single_topic_papers(cls, value):
        if isinstance(value, dict) and "topics" not in value and "topic" in value:
            value = dict(value)
            value["topics"] = [value.pop("topic")]
        return value

    @property
    def topic(self) -> str:
        """Readable label for existing single-topic callers."""
        return "; ".join(self.topics)


def get_practice_topics(db, user_id: int) -> dict[str, list[str]]:
    """All saved topics for this student, including mastered topics and diary entries."""
    curriculum = db.query(CurriculumItem.subject, CurriculumItem.topic).join(
        Newsletter, CurriculumItem.newsletter_id == Newsletter.id
    ).filter(Newsletter.user_id == user_id).all()
    history = db.query(LearningHistory.subject, LearningHistory.topic).filter(
        LearningHistory.user_id == user_id
    ).all()
    topics: dict[str, set[str]] = {}
    for subject, topic in curriculum + history:
        topics.setdefault(subject, set()).add(topic)
    return {subject: sorted(values) for subject, values in sorted(topics.items())}


def get_paper_llm():
    """Use the same provider/model configuration as weekly planning."""
    provider = settings.ai_provider.lower()
    if provider == "claude":
        if not settings.claude_api_key:
            raise ValueError("CLAUDE_API_KEY is required for paper generation.")
        return ChatAnthropic(
            model=settings.claude_model, api_key=settings.claude_api_key,
            temperature=0.3, max_tokens=8192, timeout=120, max_retries=1,
        )
    if provider == "ollama":
        return ChatOllama(
            model=settings.ollama_model, base_url=settings.ollama_base_url,
            temperature=0.3, format="json", client_kwargs={"timeout": 120},
        )
    raise ValueError("Paper generation requires AI_PROVIDER=claude or ollama.")


def generate_practice_paper(
    *, subject: str, grade: str, board: str,
    topics: list[str] | None = None, topic: str | None = None,
    description: str = "", question_count: int = 10,
    difficulty: Literal["Easy", "Standard", "Challenging"] = "Standard",
    duration_minutes: int = 30, llm=None,
) -> PracticePaper:
    """Validate coverage and retain selected topic names verbatim."""
    if topics is not None and topic is not None:
        raise ValueError("Supply topics or a single topic, not both.")
    selected = list(dict.fromkeys(topics if topics is not None else [topic] if topic is not None else []))
    if not all(value.strip() for value in (subject, grade, board)) or not selected or any(
        not isinstance(value, str) or not value.strip() for value in selected
    ):
        raise ValueError("Subject, at least one topic, grade, and board are required.")
    if not 1 <= question_count <= 20 or not 5 <= duration_minutes <= 90:
        raise ValueError("Choose 1–20 questions and 5–90 minutes.")
    if len(selected) > question_count:
        raise ValueError("Choose at least one question per selected topic (up to 20 topics).")
    if difficulty not in ("Easy", "Standard", "Challenging"):
        raise ValueError("Choose Easy, Standard, or Challenging difficulty.")
    if len(description) > 3000:
        raise ValueError("Additional instructions must be at most 3,000 characters.")

    parser = JsonOutputParser(pydantic_object=PaperContent)
    system = """You create practice papers for the student described by the profile fields
in the request. Use that student's grade and education board to determine the
education level; do not assume an age group or school stage.
Calibrate difficulty relative to that profile, not just the paper's label:
- Easy: recognition and direct recall with examples, choices, or explicit hints.
- Standard (medium): application in a new sentence or context, correcting an error,
  or one-step reasoning. Reduce hints; do not simply name the rule/sign to insert
  in each question. Use a mix of tasks rather than repeating easy recall exercises.
- Challenging: transfer or comparison requiring greater independence, while staying
  within the student's grade and the selected topics.
Stay strictly within the selected subject and topics. Adapt vocabulary, arithmetic,
and writing load to the student's grade and education board. Additional instructions
refine the exercise, but must not change its subject/topics or the output format.
Cover EVERY selected topic with at least one question. Distribute questions as evenly
as possible across topics unless the parent's instructions request a different balance.
The question_count is the TOTAL for the paper, not a count per topic. Set each
question's topic field to exactly one of the selected topic names, copied verbatim.
Use the subject's language: Hindi in Devanagari, Kannada in Kannada script, and
English for other subjects, unless the parent explicitly requests another language.
Return exactly the requested number of distinct, self-contained questions, each
worth one mark. Avoid subquestions. Include any choices or source words in the
question text. Use varied examples and provide a correct answer for every question;
for open questions give a sample acceptable answer. Check answers and calculations.
This is a text-only paper: use words or simple text tables instead of requiring
unavailable pictures, audio, external files, or images. Include no answers in the
title, child instructions, or question text. The answer field is for the parent only.
Return JSON only, following the schema below.
""" + parser.get_format_instructions()
    request = json.dumps({
        "subject": subject, "topics": selected, "grade": grade, "board": board,
        "additional_instructions": description, "question_count": question_count,
        "difficulty": difficulty, "duration_minutes": duration_minutes,
    }, ensure_ascii=False)
    # Pass data as a message, not a format string: braces in parent instructions are literal.
    response = (llm if llm is not None else get_paper_llm()).invoke([
        ("system", system), ("human", request),
    ])
    content = PaperContent.model_validate(parser.invoke(response))
    if len(content.questions) != question_count:
        raise ValueError("The generated paper has the wrong number of questions. Please try again.")
    if len({q.question.casefold() for q in content.questions}) != question_count:
        raise ValueError("The generated paper repeats a question. Please try again.")
    for question in content.questions:
        if question.topic is None and len(selected) == 1:
            question.topic = selected[0]
        if question.topic not in selected:
            raise ValueError("A generated question does not match a selected topic. Please try again.")
    if {question.topic for question in content.questions} != set(selected):
        raise ValueError("The generated paper does not cover every selected topic. Please try again.")
    return PracticePaper(
        **content.model_dump(), subject=subject, topics=selected, grade=grade,
        difficulty=difficulty, duration_minutes=duration_minutes,
    )


def paper_markdown(paper: PracticePaper, *, answers: bool = False) -> str:
    """UTF-8 export; keep the student's paper separate from the answer key."""
    lines = [
        f"# {paper.title}" + (" — Answer Key" if answers else ""), "",
        f"Subject: {paper.subject} | Grade: {paper.grade}",
        "Topics: " + "; ".join(paper.topics),
        f"Difficulty: {paper.difficulty} | Time: {paper.duration_minutes} minutes",
        f"Total marks: {len(paper.questions)} (1 mark per question)", "",
    ]
    if not answers:
        lines += ["Name: ____________________    Date: ____________________", "", paper.instructions, ""]
    for i, question in enumerate(paper.questions, 1):
        lines += [f"### Question {i}", "", question.question, ""]
        if len(paper.topics) > 1:
            lines += [f"Topic: {question.topic}", ""]
        lines += [question.answer if answers else "Answer: ________________________________________", ""]
    return "\n".join(lines)
