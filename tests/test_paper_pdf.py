import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.paper_pdf import paper_pdf
from backend.practice_paper import PracticePaper, Question


class PaperPdfTests(unittest.TestCase):
    def paper(self):
        return PracticePaper(
            title="Word Practice", instructions="Rearrange the letters.",
            subject="ENGLISH", topic="Jumbled words", grade="Class 1",
            difficulty="Easy", duration_minutes=15,
            questions=[Question(question="TAC\nClue: A pet <with whiskers> & fur.", answer="CAT")],
        )

    @unittest.skipUnless(shutil.which("pdftotext"), "Poppler is needed for PDF content checks")
    def test_student_pdf_excludes_answers_and_key_includes_them(self):
        with tempfile.TemporaryDirectory() as directory:
            for answers in (False, True):
                data = paper_pdf(self.paper(), answers=answers)
                self.assertTrue(data.startswith(b"%PDF-"))
                path = Path(directory) / "paper.pdf"
                path.write_bytes(data)
                content = subprocess.check_output(["pdftotext", str(path), "-"], text=True)
                self.assertIn("<with whiskers> & fur.", content)
                self.assertEqual("Answer: CAT" in content, answers)
                self.assertEqual("Name:" in content, not answers)

    def test_long_papers_and_indic_scripts_render(self):
        paper = self.paper()
        for title, question, answer in [
            ("हिंदी अभ्यास", "खाली जगह भरिए: कि __ ब", "किताब"),
            ("ಕನ್ನಡ ಅಭ್ಯಾಸ", "ಬಿಟ್ಟ ಅಕ್ಷರಗಳನ್ನು ತುಂಬಿರಿ: ಪು __ ಕ", "ಪುಸ್ತಕ"),
        ]:
            with self.subTest(title=title):
                paper.title = title
                paper.questions = [Question(question=question, answer=answer)] * 20
                for answers in (False, True):
                    data = paper_pdf(paper, answers=answers)
                    self.assertTrue(data.startswith(b"%PDF-"))
                    self.assertGreater(len(data), 10000)


if __name__ == "__main__":
    unittest.main()
