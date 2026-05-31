import os
import sys
import pytest

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ocr_service import OCRService


class TestOCRIntegration:
    def test_text_cleaning(self):
        dirty_text = "Q1:   A   \n\n\nQ2:   B   "
        clean = OCRService.clean_text(dirty_text)
        assert clean == "Q1: A\n\nQ2: B"

    def test_extract_answers_from_text(self):
        raw_text = (
            "Question 1: The powerhouse of the cell is mitochondria.\n"
            "Q2: Photosynthesis is how plants produce food.\n"
            "Q.3: A option"
        )
        blocks = OCRService.extract_answers_from_text(raw_text)
        assert len(blocks) == 3
        
        # Verify block mappings
        assert blocks[0]["question_number"] == 1
        assert "mitochondria" in blocks[0]["answer_text"].lower()
        
        assert blocks[1]["question_number"] == 2
        assert "photosynthesis" in blocks[1]["answer_text"].lower()
        
        assert blocks[2]["question_number"] == 3
        assert blocks[2]["answer_text"] == "A option"

    def test_pdf_extraction_fallback_simulation(self):
        # When passed dummy empty PDF/bytes, it should fallback to simulation
        result = OCRService.simulate_scanning_pipeline(b"", "biology_test.pdf")
        assert result["filename"] == "biology_test.pdf"
        assert result["status"] == "Success"
        assert "Simulation-Fallback-Active" in result["ocr_version"]
        assert len(result["blocks"]) == 4
        assert result["blocks"][0]["question_number"] == 1
        assert result["blocks"][0]["answer_text"] == "A"

    def test_non_pdf_fallback_simulation(self):
        result = OCRService.simulate_scanning_pipeline(b"", "history_final.png")
        assert result["filename"] == "history_final.png"
        assert "Simulation-Fallback-Active" in result["ocr_version"]
        assert len(result["blocks"]) == 4
        assert result["blocks"][2]["question_number"] == 3
        assert "French Revolution" in result["blocks"][2]["answer_text"]

    def test_ocr_confidence_boundings(self):
        result = OCRService.simulate_scanning_pipeline(b"", "random.pdf")
        assert 0.0 <= result["average_confidence"] <= 1.0
        for block in result["blocks"]:
            assert 0.0 <= block["confidence"] <= 1.0

    def test_extract_text_tesseract_graceful_or_success(self):
        from PIL import Image, ImageDraw
        import io
        
        # 1. Create a tiny test image
        img = Image.new("RGB", (100, 30), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((10, 10), "Q1: A", fill=(0, 0, 0))
        
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format="PNG")
        img_bytes = img_bytes_io.getvalue()
        
        # 2. Call extract_text
        try:
            res = OCRService.extract_text(img_bytes, "test_paper.png", lang="eng")
            assert "extracted_text" in res
            assert "confidence" in res
            assert "lang" in res
            assert res["lang"] == "eng"
        except RuntimeError as e:
            # If tesseract is not installed on the runner, it must raise a clear RuntimeError
            assert "Tesseract OCR binary not found" in str(e)
