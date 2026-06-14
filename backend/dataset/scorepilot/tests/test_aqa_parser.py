import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from scorepilot.config import Config
from scorepilot.parsers.aqa_parser import AQAQuestionExtractor


class TestAQAQuestionExtractor(unittest.TestCase):
    """Unit tests for the AQAQuestionExtractor parsing logic."""

    def setUp(self) -> None:
        # Create a mock config
        self.config = MagicMock(spec=Config)
        self.config.parsers = MagicMock()
        self.config.parsers.extract_tables = True
        
        self.extractor = AQAQuestionExtractor(self.config)

    @patch("scorepilot.parsers.aqa_parser.pdfplumber.open")
    @patch("scorepilot.parsers.aqa_parser.fitz.open")
    def test_extract_questions_simple(self, mock_fitz_open: MagicMock, mock_plumber_open: MagicMock) -> None:
        """Tests question extraction with basic text and marks without tables."""
        # Setup mock fitz page texts
        mock_doc = MagicMock()
        mock_fitz_open.return_value = mock_doc
        
        # 2 pages
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "4\n*04*\n0 1\nThis is introductory text.\n0 1 . 1\nWhat is a cell?  [1 mark]\n"
        
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "5\n*05*\n0 1 . 2\nExplain respiration.  [2 marks]\n"
        
        mock_doc.__len__.return_value = 2
        mock_doc.__getitem__.side_effect = [mock_page1, mock_page2]
        
        # Setup mock plumber pages (no tables)
        mock_plumber_doc = MagicMock()
        mock_plumber_open.return_value = mock_plumber_doc
        mock_p_page1 = MagicMock()
        mock_p_page1.extract_tables.return_value = []
        mock_p_page2 = MagicMock()
        mock_p_page2.extract_tables.return_value = []
        mock_plumber_doc.pages = [mock_p_page1, mock_p_page2]

        questions = self.extractor.extract_questions(Path(__file__), "Biology")
        
        # We expect 2 questions: 1.1 and 1.2
        self.assertEqual(len(questions), 2)
        
        q1 = questions[0]
        self.assertEqual(q1["board"], "AQA")
        self.assertEqual(q1["subject"], "Biology")
        self.assertEqual(q1["question_number"], "1.1")
        self.assertEqual(q1["question_text"], "This is introductory text.\n\nWhat is a cell? [1 mark]")
        self.assertEqual(q1["max_marks"], 1)

        q2 = questions[1]
        self.assertEqual(q2["question_number"], "1.2")
        self.assertEqual(q2["question_text"], "This is introductory text.\n\nExplain respiration. [2 marks]")
        self.assertEqual(q2["max_marks"], 2)

    @patch("scorepilot.parsers.aqa_parser.pdfplumber.open")
    @patch("scorepilot.parsers.aqa_parser.fitz.open")
    def test_extract_questions_with_tables(self, mock_fitz_open: MagicMock, mock_plumber_open: MagicMock) -> None:
        """Tests that tables inside questions are parsed as markdown and correctly inserted."""
        mock_doc = MagicMock()
        mock_fitz_open.return_value = mock_doc
        
        mock_page = MagicMock()
        mock_page.get_text.return_value = "4\n*04*\n0 1 . 1\nRefer to Table 1 below.\nExplain the results. [3 marks]\n"
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.side_effect = [mock_page]
        
        # Setup table data
        mock_plumber_doc = MagicMock()
        mock_plumber_open.return_value = mock_plumber_doc
        mock_p_page = MagicMock()
        
        # Standard table representation
        table_data = [
            ["Substance", "Concentration"],
            ["A", "1.2"],
            ["B", "0.8"]
        ]
        mock_p_page.extract_tables.return_value = [table_data]
        mock_plumber_doc.pages = [mock_p_page]

        questions = self.extractor.extract_questions(Path(__file__), "Chemistry")
        
        self.assertEqual(len(questions), 1)
        q = questions[0]
        
        # Table should be parsed and appended to question text
        self.assertIn("Table 1", q["question_text"])
        self.assertIn("| Substance | Concentration |", q["question_text"])
        self.assertIn("| A | 1.2 |", q["question_text"])
        self.assertIn("| B | 0.8 |", q["question_text"])
        self.assertEqual(q["max_marks"], 3)


if __name__ == "__main__":
    unittest.main()
