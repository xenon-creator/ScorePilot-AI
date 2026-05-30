import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Programmatically append the backend parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ocr_service import OCRService


class TestMultiLangOCR:
    def test_tesseract_lang_mapping(self):
        # We want to test that OCRService.simulate_scanning_pipeline calls pytesseract with the mapped lang code.
        with patch('pytesseract.image_to_string') as mock_tess, \
             patch('pytesseract.get_tesseract_version') as mock_ver, \
             patch('PIL.Image.open') as mock_img_open:
            
            mock_ver.return_value = "0.3.9"
            mock_tess.return_value = "Q1: A\nQ2: B"
            
            # Spanish (es) -> spa
            OCRService.simulate_scanning_pipeline(b"fake_image_bytes", "biology.png", language="es")
            mock_tess.assert_any_call(mock_img_open.return_value, lang="spa")
            
            # French (fr) -> fra
            OCRService.simulate_scanning_pipeline(b"fake_image_bytes", "biology.png", language="fr")
            mock_tess.assert_any_call(mock_img_open.return_value, lang="fra")
            
            # German (de) -> deu
            OCRService.simulate_scanning_pipeline(b"fake_image_bytes", "biology.png", language="de")
            mock_tess.assert_any_call(mock_img_open.return_value, lang="deu")
            
            # Default/English (en) -> eng
            OCRService.simulate_scanning_pipeline(b"fake_image_bytes", "biology.png", language="en")
            mock_tess.assert_any_call(mock_img_open.return_value, lang="eng")

    def test_google_vision_language_hints(self):
        # We want to test that Google Cloud Vision documents text detection is called with language hints.
        with patch('google.cloud.vision.ImageAnnotatorClient') as mock_client_cls, \
             patch('app.core.config.settings.GOOGLE_APPLICATION_CREDENTIALS', 'fake_creds'), \
             patch('google.cloud.vision.ImageContext') as mock_context_cls, \
             patch('google.cloud.vision.Image') as mock_image_cls:
            
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            
            # Simulate Vision response
            mock_response = MagicMock()
            mock_response.full_text_annotation.text = "Q1: A\nQ2: B"
            mock_response.error.message = ""
            mock_client.document_text_detection.return_value = mock_response
            
            OCRService.simulate_scanning_pipeline(b"fake_image_bytes", "biology.png", language="es")
            
            # Verify ImageContext was created with language hints
            mock_context_cls.assert_called_with(language_hints=["es"])
            
            # Verify document_text_detection was triggered with the context
            mock_client.document_text_detection.assert_called_once()

    def test_fallback_simulation_localized_texts(self):
        # Test biology fallbacks in different languages
        res_es = OCRService.simulate_scanning_pipeline(b"", "biology.png", language="es")
        assert "La mitocondria es la central" in res_es["raw_text"]
        
        res_fr = OCRService.simulate_scanning_pipeline(b"", "biology.png", language="fr")
        assert "La mitochondrie est la centrale" in res_fr["raw_text"]
        
        res_de = OCRService.simulate_scanning_pipeline(b"", "biology.png", language="de")
        assert "Das Mitochondrium ist das Kraftwerk" in res_de["raw_text"]
        
        # Test history fallbacks in different languages
        res_es_hist = OCRService.simulate_scanning_pipeline(b"", "history.png", language="es")
        assert "La Revolución Francesa comenzó" in res_es_hist["raw_text"]
        
        res_fr_hist = OCRService.simulate_scanning_pipeline(b"", "history.png", language="fr")
        assert "La Révolution française a commencé" in res_fr_hist["raw_text"]
        
        res_de_hist = OCRService.simulate_scanning_pipeline(b"", "history.png", language="de")
        assert "Die Französische Revolution begann" in res_de_hist["raw_text"]
