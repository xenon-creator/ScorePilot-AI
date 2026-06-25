import os
import io
import sys
import pytest
from unittest import mock
from PIL import Image

# 1. Inject mocks into sys.modules so imports in surya_ocr_service don't fail during testing
mock_surya = mock.MagicMock()
mock_surya_ocr = mock.MagicMock()
mock_surya_det_model = mock.MagicMock()
mock_surya_rec_model = mock.MagicMock()
mock_surya_rec_processor = mock.MagicMock()
mock_paddleocr = mock.MagicMock()

sys.modules['surya'] = mock_surya
sys.modules['surya.ocr'] = mock_surya_ocr
sys.modules['surya.model'] = mock.MagicMock()
sys.modules['surya.model.detection'] = mock.MagicMock()
sys.modules['surya.model.detection.model'] = mock_surya_det_model
sys.modules['surya.model.recognition'] = mock.MagicMock()
sys.modules['surya.model.recognition.model'] = mock_surya_rec_model
sys.modules['surya.model.recognition.processor'] = mock_surya_rec_processor
sys.modules['paddleocr'] = mock_paddleocr

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.surya_ocr_service import SuryaOCRService
from app.services.ocr_service import OCRService

class TestSuryaOCR:
    def test_text_cleaning_basic(self):
        dirty = "Q1:   Mitcohondria   \n\n\nQ2:   Photosynthesis   "
        clean = SuryaOCRService.clean_ocr_text(dirty)
        assert clean == "Q1: Mitcohondria\n\nQ2: Photosynthesis"

    def test_text_cleaning_scientific_terms(self):
        text_with_formulas = "We found H_2O and CO_2 in the solution. E = mc^2."
        clean = SuryaOCRService.clean_ocr_text(text_with_formulas)
        assert "H_2O" in clean
        assert "CO_2" in clean
        assert "E = mc^2" in clean

    def test_text_cleaning_artifacts(self):
        text = "Hello\n|\nWorld\n_\n~"
        clean = SuryaOCRService.clean_ocr_text(text)
        assert clean == "Hello\nWorld"

    @mock.patch.dict(os.environ, {"USE_MOCK_OCR": "true"})
    def test_mock_ocr_biology(self):
        res = SuryaOCRService.extract_text(b"fakebytes", "biology_test.jpg")
        assert res["success"] is True
        assert res["ocr_engine"] == "MockOCR"
        assert "Mitochondria" in res["text"]

    @mock.patch.dict(os.environ, {"USE_MOCK_OCR": "true"})
    def test_mock_ocr_pdf(self):
        res = SuryaOCRService.extract_text(b"fakebytes", "exam_paper.pdf")
        assert res["success"] is True
        assert res["ocr_engine"] == "MockOCR"
        assert "Photosynthesis" in res["text"]

    @mock.patch.dict(os.environ, {"USE_MOCK_OCR": "false"})
    def test_surya_success_flow(self):
        class MockTextLine:
            def __init__(self, text, confidence):
                self.text = text
                self.confidence = confidence

        class MockPrediction:
            def __init__(self, lines):
                self.text_lines = lines

        # Set up Surya OCR Mock return value
        mock_surya_ocr.run_ocr.return_value = [
            MockPrediction([
                MockTextLine("This is handwritten page text", 0.96),
                MockTextLine("Second line of student answer", 0.94)
            ])
        ]
        
        # Mock load methods
        mock_surya_det_model.load_model.return_value = mock.Mock()
        mock_surya_det_model.load_processor.return_value = mock.Mock()
        mock_surya_rec_model.load_model.return_value = mock.Mock()
        mock_surya_rec_processor.load_processor.return_value = mock.Mock()

        img = Image.new("RGB", (100, 30), color=(255, 255, 255))
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format="PNG")
        img_bytes = img_bytes_io.getvalue()
        
        # Reset cache
        SuryaOCRService._det_model = mock.Mock()
        SuryaOCRService._rec_model = mock.Mock()
        SuryaOCRService._paddle_ocr = None
        
        res = SuryaOCRService.extract_text(img_bytes, "notebook_photo.png")
        assert res["success"] is True
        assert res["ocr_engine"] == "Surya"
        assert res["ocr_confidence"] == 0.95
        assert "handwritten page text" in res["text"]

    @mock.patch.dict(os.environ, {"USE_MOCK_OCR": "false"})
    def test_surya_failure_paddle_fallback_success(self):
        # Set up Surya OCR failure
        mock_surya_ocr.run_ocr.side_effect = Exception("Surya CUDA OOM")
        
        # Set up PaddleOCR Mock
        mock_paddle_instance = mock.Mock()
        mock_paddle_instance.ocr.return_value = [
            [
                [ [[0,0],[10,0],[10,10],[0,10]], ("Paddle text line", 0.88) ]
            ]
        ]
        mock_paddleocr.PaddleOCR.return_value = mock_paddle_instance
        
        # Clear/Reset service cache
        SuryaOCRService._det_model = mock.Mock()
        SuryaOCRService._rec_model = mock.Mock()
        SuryaOCRService._paddle_ocr = None
        
        img = Image.new("RGB", (100, 30), color=(255, 255, 255))
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format="PNG")
        img_bytes = img_bytes_io.getvalue()
        
        res = SuryaOCRService.extract_text(img_bytes, "notebook_photo.png")
        assert res["success"] is True
        assert res["ocr_engine"] == "PaddleOCR"
        assert "Paddle text line" in res["text"]
        assert res["ocr_confidence"] == 0.88
        
        # Restore side effect
        mock_surya_ocr.run_ocr.side_effect = None

    @mock.patch.dict(os.environ, {"USE_MOCK_OCR": "false"})
    @mock.patch("app.services.ocr_service.OCRService.extract_text")
    def test_all_deep_learning_fail_tesseract_fallback_success(self, mock_tesseract_extract):
        # Surya and Paddle both fail
        mock_surya_ocr.run_ocr.side_effect = Exception("Surya failed")
        mock_paddleocr.PaddleOCR.side_effect = Exception("Paddle failed")
        
        # Clear/Reset service cache
        SuryaOCRService._det_model = mock.Mock()
        SuryaOCRService._rec_model = mock.Mock()
        SuryaOCRService._paddle_ocr = None
        
        # Mock Tesseract fallback
        mock_tesseract_extract.return_value = {
            "extracted_text": "Tesseract fallback text",
            "confidence": 0.72,
            "lang": "eng"
        }
        
        img = Image.new("RGB", (100, 30), color=(255, 255, 255))
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format="PNG")
        img_bytes = img_bytes_io.getvalue()
        
        res = SuryaOCRService.extract_text(img_bytes, "student_handwriting.png")
        assert res["success"] is True
        assert res["ocr_engine"] == "Tesseract-Fallback"
        assert "Tesseract fallback text" in res["text"]
        assert res["ocr_confidence"] == 0.72
        
        # Restore side effects
        mock_surya_ocr.run_ocr.side_effect = None
        mock_paddleocr.PaddleOCR.side_effect = None

    @mock.patch.dict(os.environ, {"USE_MOCK_OCR": "false"})
    @mock.patch("app.services.ocr_service.OCRService.extract_text")
    def test_all_fail_returns_error(self, mock_tesseract_extract):
        mock_surya_ocr.run_ocr.side_effect = Exception("Surya failed")
        mock_paddleocr.PaddleOCR.side_effect = Exception("Paddle failed")
        mock_tesseract_extract.side_effect = Exception("Tesseract binary not found")
        
        # Clear/Reset service cache
        SuryaOCRService._det_model = mock.Mock()
        SuryaOCRService._rec_model = mock.Mock()
        SuryaOCRService._paddle_ocr = None
        
        img = Image.new("RGB", (100, 30), color=(255, 255, 255))
        img_bytes_io = io.BytesIO()
        img.save(img_bytes_io, format="PNG")
        img_bytes = img_bytes_io.getvalue()
        
        res = SuryaOCRService.extract_text(img_bytes, "student_handwriting.png")
        assert res["success"] is False
        assert "All OCR engines failed" in res["error"]
        
        # Restore side effects
        mock_surya_ocr.run_ocr.side_effect = None
        mock_paddleocr.PaddleOCR.side_effect = None
