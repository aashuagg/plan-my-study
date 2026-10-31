import json
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from backend.database import Base
from backend.models import CurriculumItem, LearningHistory, Newsletter, User
from backend.practice_paper import (
    generate_practice_paper, get_practice_topics, paper_markdown,
)


def model_response(questions=None):
    return AIMessage(content=json.dumps({
        "title": "Word practice", "instructions": "Fill in each blank.",
        "questions": questions if questions is not None else [
            {"question": "I ___ happy.", "answer": "am"},
            {"question": "She ___ happy.", "answer": "is"},
        ],
    }))


def sample_paper():
    return generate_practice_paper(
        subject="ENGLISH", topic="am, is, are", grade="Class 1", board="CBSE",
        question_count=2, llm=Mock(invoke=Mock(return_value=model_response())),
    )


class PaperGenerationTests(unittest.TestCase):
    def test_multiple_topics_are_sent_and_covered_in_exports(self):
        topics = ["Naming words", "Action words"]
        llm = Mock(invoke=Mock(return_value=model_response([
            {"question": "Name a pet.", "answer": "Cat", "topic": topics[0]},
            {"question": "What do birds do?", "answer": "Fly", "topic": topics[1]},
        ])))
        paper = generate_practice_paper(subject="ENGLISH", topics=topics, grade="Class 1",
                                        board="CBSE", question_count=2, llm=llm)
        request = json.loads(llm.invoke.call_args.args[0][1][1])
        self.assertEqual(request["topics"], topics)
        self.assertEqual(paper.topics, topics)
        for answers in (False, True):
            for topic in topics:
                self.assertIn(topic, paper_markdown(paper, answers=answers))

    def test_rejects_unknown_or_uncovered_topics(self):
        for second_topic in ("Naming words", "Unselected topic", None):
            llm = Mock(invoke=Mock(return_value=model_response([
                {"question": "Name a pet.", "answer": "Cat", "topic": "Naming words"},
                {"question": "Name a fruit.", "answer": "Apple", "topic": second_topic},
            ])))
            with self.subTest(second_topic=second_topic), self.assertRaises(ValueError):
                generate_practice_paper(subject="ENGLISH", topics=["Naming words", "Action words"],
                                        grade="Class 1", board="CBSE", question_count=2, llm=llm)

    def test_rejects_empty_topics_and_insufficient_questions_before_llm_call(self):
        for topics, count in (([], 2), (["Naming words", "Action words"], 1)):
            llm = Mock()
            with self.subTest(topics=topics), self.assertRaises(ValueError):
                generate_practice_paper(subject="ENGLISH", topics=topics, grade="Class 1",
                                        board="CBSE", question_count=count, llm=llm)
            llm.invoke.assert_not_called()

    def test_older_paper_session_is_readable(self):
        from backend.practice_paper import PracticePaper
        old = sample_paper().model_dump()
        old["topic"] = old.pop("topics")[0]
        self.assertEqual(PracticePaper.model_validate(old).topics, ["am, is, are"])

    def test_prompt_keeps_selection_and_literal_parent_instructions(self):
        llm = Mock(invoke=Mock(return_value=model_response()))
        paper = generate_practice_paper(
            subject="ENGLISH", topic="am, is, are", grade="Class 9", board="ICSE",
            description='Use {blanks} and "short" sentences.', question_count=2, llm=llm,
        )
        request = json.loads(llm.invoke.call_args.args[0][1][1])
        self.assertEqual((request["grade"], request["board"]), ("Class 9", "ICSE"))
        self.assertEqual(paper.grade, "Class 9")
        system = llm.invoke.call_args.args[0][0][1]
        self.assertNotIn("primary-school", system)
        self.assertIn("student's grade and education board", system)
        self.assertEqual(request["additional_instructions"], 'Use {blanks} and "short" sentences.')
        self.assertEqual((paper.subject, paper.topic), ("ENGLISH", "am, is, are"))

    def test_rejects_wrong_count_duplicate_and_empty_answer(self):
        variants = [
            [{"question": "A?", "answer": "a"}],
            [{"question": "Same?", "answer": "a"}, {"question": "same?", "answer": "a"}],
            [{"question": "A?", "answer": " "}, {"question": "B?", "answer": "b"}],
        ]
        for questions in variants:
            with self.subTest(questions=questions), self.assertRaises(ValueError):
                generate_practice_paper(
                    subject="HINDI", topic="Words", grade="Class 1", board="CBSE",
                    question_count=2, llm=Mock(invoke=Mock(return_value=model_response(questions))),
                )

    def test_invalid_input_does_not_call_provider(self):
        llm = Mock()
        with self.assertRaises(ValueError):
            generate_practice_paper(
                subject="ENGLISH", topic="Words", grade="Class 1", board="CBSE",
                question_count=21, llm=llm,
            )
        llm.invoke.assert_not_called()

    def test_student_export_has_no_answer_key_and_supports_unicode(self):
        paper = sample_paper()
        paper.questions[0].question = "ಕನ್ನಡ: ___"
        paper.questions[0].answer = "ಉತ್ತರ"
        student = paper_markdown(paper)
        self.assertIn("ಕನ್ನಡ", student)
        self.assertNotIn("ಉತ್ತರ", student)
        self.assertIn("ಉತ್ತರ", paper_markdown(paper, answers=True))
        self.assertEqual(student.encode("utf-8").decode("utf-8"), student)

    def test_provider_selection_and_missing_key(self):
        from backend.practice_paper import get_paper_llm
        with patch("backend.practice_paper.settings", SimpleNamespace(
            ai_provider="claude", claude_api_key="",
        )), self.assertRaises(ValueError):
            get_paper_llm()
        with patch("backend.practice_paper.settings", SimpleNamespace(
            ai_provider="ollama", ollama_model="local", ollama_base_url="http://localhost:11434",
        )), patch("backend.practice_paper.ChatOllama") as constructor:
            self.assertIs(get_paper_llm(), constructor.return_value)
            self.assertEqual(constructor.call_args.kwargs["format"], "json")


class TopicSelectionTests(unittest.TestCase):
    def test_scopes_topics_to_student_and_deduplicates_without_progress_changes(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            for user_id in (1, 2):
                db.add(User(id=user_id, name=str(user_id), grade="Class 1", board="CBSE",
                            daily_duration_minutes=30, weekly_frequency=6, subjects=["ENGLISH"]))
            first = Newsletter(user_id=1, month="Diary", year=0)
            other = Newsletter(user_id=2, month="October", year=2026)
            db.add_all([first, other])
            db.flush()
            db.add_all([
                CurriculumItem(newsletter_id=first.id, subject="ENGLISH", topic="Words", start_date=date.today()),
                CurriculumItem(newsletter_id=other.id, subject="ENGLISH", topic="Private topic", start_date=date.today()),
                LearningHistory(user_id=1, subject="ENGLISH", topic="Words", next_review=date.today(), graduated=True),
                LearningHistory(user_id=1, subject="HINDI", topic="किताब", next_review=date.today()),
            ])
            db.commit()
            self.assertEqual(get_practice_topics(db, 1), {"ENGLISH": ["Words"], "HINDI": ["किताब"]})
            self.assertFalse(db.new or db.dirty or db.deleted)
        engine.dispose()


class PaperPageTests(unittest.TestCase):
    SCRIPT = """
from types import SimpleNamespace
from frontend.modules.practice_paper import show_practice_paper_page
show_practice_paper_page(None, SimpleNamespace(id=1, grade='Class 1', board='CBSE'))
"""

    def test_generate_display_download_rerun_and_subject_change(self):
        with patch("frontend.modules.practice_paper.get_practice_topics", return_value={
            "ENGLISH": ["am, is, are"], "HINDI": ["Words"],
        }), patch("frontend.modules.practice_paper.generate_practice_paper", return_value=sample_paper()) as generate:
            app = AppTest.from_string(self.SCRIPT).run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            generate.assert_called_once()
            self.assertEqual(generate.call_args.kwargs["grade"], "Class 1")
            self.assertEqual(generate.call_args.kwargs["board"], "CBSE")
            self.assertEqual(len(app.get("download_button")), 4)
            self.assertEqual(len(app.expander), 1)
            app.run()
            generate.assert_called_once()
            self.assertEqual(len(app.get("download_button")), 4)
            app.selectbox[0].select("HINDI").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.multiselect[0].value, ["Words"])
            self.assertEqual(len(app.get("download_button")), 0)

    def test_select_multiple_topics_and_hide_result_when_selection_changes(self):
        paper = sample_paper()
        paper.topics = ["am, is, are", "Naming words"]
        paper.questions[0].topic = paper.topics[0]
        paper.questions[1].topic = paper.topics[1]
        with patch("frontend.modules.practice_paper.get_practice_topics", return_value={
            "ENGLISH": paper.topics, "HINDI": ["Words"],
        }), patch("frontend.modules.practice_paper.generate_practice_paper", return_value=paper) as generate:
            app = AppTest.from_string(self.SCRIPT).run()
            app.multiselect[0].set_value(paper.topics).run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(generate.call_args.kwargs["topics"], paper.topics)
            self.assertEqual(len(app.get("download_button")), 4)
            app.multiselect[0].set_value([paper.topics[0]]).run()
            self.assertEqual(len(app.get("download_button")), 0)
            app.multiselect[0].set_value([]).run()
            self.assertTrue(app.button[0].disabled)
            generate.assert_called_once()

    def test_empty_topics(self):
        with patch("frontend.modules.practice_paper.get_practice_topics", return_value={}):
            app = AppTest.from_string(self.SCRIPT).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.info), 1)
            self.assertEqual(len(app.button), 0)

    def test_pdf_failure_keeps_screen_preview_and_markdown_downloads(self):
        with patch("frontend.modules.practice_paper.get_practice_topics", return_value={"ENGLISH": ["am, is, are"]}), patch(
            "frontend.modules.practice_paper.generate_practice_paper", return_value=sample_paper(),
        ), patch("frontend.modules.practice_paper._pdf_downloads", side_effect=RuntimeError("PDF unavailable")):
            app = AppTest.from_string(self.SCRIPT).run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("I ___ happy." in element.value for element in app.markdown))
            self.assertEqual(len(app.error), 1)
            self.assertEqual(len(app.get("download_button")), 2)

    def test_generation_error_is_recoverable(self):
        with patch("frontend.modules.practice_paper.get_practice_topics", return_value={"ENGLISH": ["Words"]}), patch(
            "frontend.modules.practice_paper.generate_practice_paper", side_effect=RuntimeError("offline"),
        ):
            app = AppTest.from_string(self.SCRIPT).run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.error), 1)
            self.assertEqual(len(app.button), 1)


if __name__ == "__main__":
    unittest.main()
