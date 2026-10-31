"""Practice-paper page: select a saved topic, generate, and download."""

import logging

import streamlit as st

from backend.practice_paper import (
    PracticePaper, generate_practice_paper, get_practice_topics, paper_markdown,
)
from backend.paper_pdf import paper_pdf

logger = logging.getLogger(__name__)


@st.cache_data(show_spinner=False, max_entries=32)
def _pdf_downloads(paper_json):
    paper = PracticePaper.model_validate_json(paper_json)
    return paper_pdf(paper), paper_pdf(paper, answers=True)


def show_practice_paper_page(db, user):
    st.title("📝 Practice Papers")
    st.caption("Choose one or more topics from the same subject and describe the practice you want. Generating a paper does not change review ratings.")
    topics = get_practice_topics(db, user.id)
    if not topics:
        st.info("Add topics through Upload Newsletter or Add Diary Entry to create a practice paper.")
        return

    subject = st.selectbox("Subject", list(topics), key="paper_subject")
    selected_topics = st.multiselect(
        "Topics", topics[subject], default=topics[subject][:1],
        max_selections=20, key=f"paper_topics_{subject}",
    )
    if not selected_topics:
        st.info("Select at least one topic to generate a paper.")
    with st.form("practice_paper_form"):
        description = st.text_area(
            "Additional instructions (optional)", max_chars=3000,
            placeholder="For example: use short sentences, include fill-in-the-blanks, and focus on am/is/are.",
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            question_count = st.number_input(
                "Total number of questions", min_value=max(1, len(selected_topics)),
                max_value=20, value=max(10, len(selected_topics)),
                help="Total for the whole paper, with at least one question per selected topic.",
            )
        with col2:
            difficulty = st.selectbox("Difficulty", ["Easy", "Standard", "Challenging"], index=1)
        with col3:
            duration = st.number_input("Time (minutes)", min_value=5, max_value=90, value=30, step=5)
        submitted = st.form_submit_button("Generate practice paper", type="primary", disabled=not selected_topics)

    result_key = f"practice_paper_result_{user.id}"
    if submitted:
        try:
            with st.spinner("Creating your practice paper…"):
                paper = generate_practice_paper(
                    subject=subject, topics=selected_topics, grade=user.grade, board=user.board,
                    description=description, question_count=int(question_count),
                    difficulty=difficulty, duration_minutes=int(duration),
                )
            st.session_state[result_key] = paper.model_dump()
        except Exception:
            logger.exception("Practice paper generation failed")
            st.error("Could not generate a valid practice paper. Please try again. If this continues, check the configured AI provider and connection.")

    saved = st.session_state.get(result_key)
    if not saved:
        return
    paper = PracticePaper.model_validate(saved)
    if paper.subject != subject or set(paper.topics) != set(selected_topics):
        return
    st.divider()
    st.caption("Last generated paper for these topics. Review the questions and answers before using it.")
    student_copy = paper_markdown(paper)
    answer_key = paper_markdown(paper, answers=True)
    st.markdown(student_copy)
    with st.expander("Answer key — for the parent"):
        st.markdown(answer_key)
    try:
        student_pdf, answers_pdf = _pdf_downloads(paper.model_dump_json())
    except Exception:
        logger.exception("Practice paper PDF export failed")
        st.error("PDF export is unavailable. You can still read the paper here and download Markdown.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download paper as PDF", student_pdf,
                               file_name="practice-paper.pdf", mime="application/pdf")
        with col2:
            st.download_button("Download answer key as PDF", answers_pdf,
                               file_name="answer-key.pdf", mime="application/pdf")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Download paper as Markdown", student_copy.encode("utf-8"),
                           file_name="practice-paper.md", mime="text/markdown; charset=utf-8")
    with col2:
        st.download_button("Download answer key as Markdown", answer_key.encode("utf-8"),
                           file_name="answer-key.md", mime="text/markdown; charset=utf-8")
