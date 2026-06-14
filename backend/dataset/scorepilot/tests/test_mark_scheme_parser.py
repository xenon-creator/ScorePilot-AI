import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from scorepilot.config import Config
from scorepilot.parsers.pdf_engine import ParsedDocument
from scorepilot.parsers.mark_scheme_parser import MarkSchemeParser


class TestMarkSchemeParser(unittest.TestCase):
    """Unit tests for the MarkSchemeParser class."""

    def setUp(self) -> None:
        self.config = MagicMock(spec=Config)
        self.parser = MarkSchemeParser(self.config)

    @patch("scorepilot.parsers.mark_scheme_parser.pdfplumber.open")
    def test_parse_aqa(self, mock_plumber_open: MagicMock) -> None:
        """Tests that AQA mark schemes are parsed correctly from tables."""
        # Mock pdfplumber structures
        mock_pdf = MagicMock()
        mock_pdf.__enter__.return_value = mock_pdf
        mock_plumber_open.return_value = mock_pdf

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Question 1.1\nLevel descriptors table below."
        
        # 5-column table representing AQA mark scheme structure
        table_data = [
            ["Q", "Answer", "Extra information", "Mark", "AO"],
            ["1.1", "mention sunlight", "accept light", "1", "AO1"],
            ["", "carbon dioxide", "", "1", "AO2"]
        ]
        mock_page.extract_tables.return_value = [table_data]
        mock_pdf.pages = [mock_page]

        # Call parser
        doc = ParsedDocument(file_path=Path("dummy.pdf"), pages=[])
        ms = self.parser.parse(
            doc=doc,
            subject="Biology",
            level="GCSE",
            year=2023,
            board="AQA",
            paper_code="8461/1H"
        )

        self.assertEqual(ms.board, "AQA")
        self.assertEqual(ms.subject, "Biology")
        self.assertEqual(ms.year, 2023)
        self.assertEqual(ms.paper_code, "8461/1H")
        self.assertEqual(len(ms.items), 1)

        item = ms.items[0]
        self.assertEqual(item.question_number, "1.1")
        self.assertIn("mention sunlight", item.marking_guidelines)
        self.assertIn("carbon dioxide", item.marking_guidelines)
        self.assertEqual(item.metadata.get("marks"), 2)


if __name__ == "__main__":
    unittest.main()
