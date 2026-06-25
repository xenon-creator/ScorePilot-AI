import os
import io
import re
import time
import logging
from typing import Dict, Any, List, Optional
from PIL import Image

logger = logging.getLogger(__name__)

class SuryaOCRService:
    _instance = None
    
    # Class attributes to cache models
    _det_model = None
    _det_processor = None
    _rec_model = None
    _rec_processor = None
    _paddle_ocr = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(SuryaOCRService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    @classmethod
    def load_models(cls):
        """Loads Surya and/or Paddle models in memory. Thread-safe once loaded."""
        if os.getenv("USE_MOCK_OCR", "false").lower() == "true":
            logger.info("USE_MOCK_OCR is enabled. Skipping model weight loading.")
            return

        # Load Surya detection & recognition models if not already loaded
        if cls._det_model is None or cls._rec_model is None:
            logger.info("Initializing Surya OCR models...")
            try:
                from surya.model.detection.model import load_model as load_det_model, load_processor as load_det_processor
                from surya.model.recognition.model import load_model as load_rec_model
                from surya.model.recognition.processor import load_processor as load_rec_processor
                
                device = os.getenv("SURYA_DEVICE", "cpu")
                logger.info(f"Loading Surya models on device: {device}")
                
                cls._det_model = load_det_model()
                cls._det_processor = load_det_processor()
                cls._rec_model = load_rec_model()
                cls._rec_processor = load_rec_processor()
                logger.info("Surya OCR models loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load Surya OCR models: {e}. Will fallback to PaddleOCR.")
                
        # Load PaddleOCR model if not already loaded
        if cls._paddle_ocr is None:
            logger.info("Initializing PaddleOCR...")
            try:
                from paddleocr import PaddleOCR
                cls._paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
                logger.info("PaddleOCR model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load PaddleOCR model: {e}")

    @classmethod
    def clean_ocr_text(cls, text: str) -> str:
        """
        Cleans duplicate spaces, normalizes line breaks and punctuation, removes OCR artifacts,
        and preserves scientific terms (e.g. CO2, H2O, formulas).
        """
        if not text:
            return ""
        
        # 1. Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # 2. Fix curly quotes and apostrophes
        text = re.sub(r'[“”]', '"', text)
        text = re.sub(r'[‘’]', "'", text)
        
        # 3. Clean line by line
        lines = []
        for line in text.split("\n"):
            # Remove duplicate spaces and tabs (but preserve word/symbol spacing)
            cleaned_line = re.sub(r'[ \t]+', ' ', line).strip()
            
            # Remove lines that contain only stray OCR scanner artifacts
            if cleaned_line in ['|', '~', '_', '\\', '°', '•', '-']:
                continue
                
            # Remove lines that are just repeated non-alphanumeric characters
            if re.match(r'^[^a-zA-Z0-9\s]{3,}$', cleaned_line):
                # Check if it looks like a math/science equation or formula (contains digits, =, +, etc.)
                if not any(char in cleaned_line for char in ['=', '+', '-', '*', '/', '>', '<']):
                    continue
            
            lines.append(cleaned_line)
            
        # 4. Recombine lines
        cleaned_text = "\n".join(lines)
        
        # 5. Fix multiple consecutive newlines (max 2)
        cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)
        
        # 6. Remove duplicate spaces across the whole text
        cleaned_text = re.sub(r' +', ' ', cleaned_text)
        
        return cleaned_text.strip()

    @classmethod
    def extract_text(cls, file_content: bytes, filename: str, langs: List[str] = None) -> Dict[str, Any]:
        """
        Extracts text from given file content (JPG, JPEG, PNG, PDF) using Surya OCR,
        with PaddleOCR and Tesseract/Claude as fallbacks.
        """
        start_time = time.time()
        logger.info(f"SuryaOCRService: OCR started for {filename} ({len(file_content)} bytes)")
        
        if not file_content:
            return {"success": False, "error": "Empty file content", "text": "", "raw_text": "", "cleaned_text": "", "ocr_engine": "None", "ocr_confidence": 0.0}
            
        # 1. Validation of file format
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext not in ("jpg", "jpeg", "png", "pdf"):
            logger.error(f"Unsupported file format: {ext}")
            return {"success": False, "error": f"Unsupported file format: {ext}", "text": "", "raw_text": "", "cleaned_text": "", "ocr_engine": "None", "ocr_confidence": 0.0}
            
        # 2. Check Mock Mode
        if os.getenv("USE_MOCK_OCR", "false").lower() == "true":
            logger.info("Using mock OCR extraction.")
            mock_text = cls._get_mock_text(filename)
            duration = time.time() - start_time
            logger.info(f"OCR completed (Mock) | Time: {duration:.2f}s | Text length: {len(mock_text)}")
            return {
                "success": True,
                "text": mock_text,
                "raw_text": mock_text,
                "cleaned_text": mock_text,
                "ocr_engine": "MockOCR",
                "ocr_confidence": 0.95,
                "processing_time": duration
            }

        # 3. Convert PDF pages or open image
        images: List[Image.Image] = []
        try:
            if ext == "pdf":
                from pdf2image import convert_from_bytes
                images = convert_from_bytes(file_content)
                logger.info(f"Converted PDF to {len(images)} images.")
            else:
                img = Image.open(io.BytesIO(file_content))
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images = [img]
        except Exception as e:
            logger.error(f"Failed to convert or open image/PDF: {e}")
            return {"success": False, "error": f"Failed to load image: {e}", "text": "", "raw_text": "", "cleaned_text": "", "ocr_engine": "None", "ocr_confidence": 0.0}

        # 4. Try Surya OCR
        try:
            cls.load_models()  # Ensure models are loaded
            
            if cls._det_model is not None and cls._rec_model is not None:
                logger.info("Running Surya OCR...")
                from surya.ocr import run_ocr
                
                surya_langs = [langs or ["en"]] * len(images)
                
                predictions = run_ocr(
                    images, 
                    surya_langs, 
                    cls._det_model, 
                    cls._det_processor, 
                    cls._rec_model, 
                    cls._rec_processor
                )
                
                all_text_lines = []
                all_confidences = []
                
                for pred in predictions:
                    for line in pred.text_lines:
                        all_text_lines.append(line.text)
                        if hasattr(line, "confidence") and line.confidence is not None:
                            all_confidences.append(line.confidence)
                            
                raw_text = "\n".join(all_text_lines)
                cleaned_text = cls.clean_ocr_text(raw_text)
                avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.90
                
                duration = time.time() - start_time
                logger.info(
                    f"OCR Completed | OCR Engine: Surya | Pages: {len(images)} | "
                    f"Characters: {len(cleaned_text)} | Time: {duration:.2f}s | "
                    f"Confidence: {avg_confidence:.2f}"
                )
                return {
                    "success": True,
                    "text": cleaned_text,
                    "raw_text": raw_text,
                    "cleaned_text": cleaned_text,
                    "ocr_engine": "Surya",
                    "ocr_confidence": round(avg_confidence, 2),
                    "processing_time": duration
                }
            else:
                raise RuntimeError("Surya OCR models not loaded.")
                
        except Exception as surya_err:
            logger.warning(f"Surya OCR failed: {surya_err}. Trying PaddleOCR fallback...")
            
            # 5. Try PaddleOCR Fallback
            try:
                cls.load_models()
                if cls._paddle_ocr is not None:
                    logger.info("Running PaddleOCR fallback...")
                    import numpy as np
                    
                    all_text_lines = []
                    all_confidences = []
                    
                    for img in images:
                        img_np = np.array(img)
                        result = cls._paddle_ocr.ocr(img_np, cls=True)
                        if result:
                            for line in result:
                                if line:
                                    for word_info in line:
                                        text = word_info[1][0]
                                        conf = word_info[1][1]
                                        all_text_lines.append(text)
                                        all_confidences.append(conf)
                                        
                    raw_text = "\n".join(all_text_lines)
                    cleaned_text = cls.clean_ocr_text(raw_text)
                    avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.85
                    
                    duration = time.time() - start_time
                    logger.info(
                        f"OCR Completed | OCR Engine: PaddleOCR | Pages: {len(images)} | "
                        f"Characters: {len(cleaned_text)} | Time: {duration:.2f}s | "
                        f"Confidence: {avg_confidence:.2f}"
                    )
                    return {
                        "success": True,
                        "text": cleaned_text,
                        "raw_text": raw_text,
                        "cleaned_text": cleaned_text,
                        "ocr_engine": "PaddleOCR",
                        "ocr_confidence": round(avg_confidence, 2),
                        "processing_time": duration
                    }
                else:
                    raise RuntimeError("PaddleOCR model not loaded.")
            except Exception as paddle_err:
                logger.warning(f"PaddleOCR fallback failed: {paddle_err}. Trying secondary Tesseract/Claude fallback...")
                
                # 6. Try Secondary Tesseract/Claude Fallback
                try:
                    from app.services.ocr_service import OCRService
                    logger.info("Running secondary Tesseract/Claude OCR fallback...")
                    res = OCRService.extract_text(file_content, filename)
                    raw_text = res.get("extracted_text", "") or res.get("raw_text", "")
                    cleaned_text = cls.clean_ocr_text(raw_text)
                    avg_confidence = res.get("confidence", 0.75)
                    engine_name = "Tesseract-Fallback"
                    
                    duration = time.time() - start_time
                    logger.info(
                        f"OCR Completed | OCR Engine: {engine_name} | Pages: {len(images)} | "
                        f"Characters: {len(cleaned_text)} | Time: {duration:.2f}s | "
                        f"Confidence: {avg_confidence:.2f}"
                    )
                    return {
                        "success": True,
                        "text": cleaned_text,
                        "raw_text": raw_text,
                        "cleaned_text": cleaned_text,
                        "ocr_engine": engine_name,
                        "ocr_confidence": round(avg_confidence, 2),
                        "processing_time": duration
                    }
                except Exception as secondary_err:
                    logger.error(f"All OCR options failed. Final error: {secondary_err}")
                    return {
                        "success": False,
                        "error": f"All OCR engines failed: {secondary_err}",
                        "text": "",
                        "raw_text": "",
                        "cleaned_text": "",
                        "ocr_engine": "None",
                        "ocr_confidence": 0.0
                    }

    @classmethod
    def _get_mock_text(cls, filename: str) -> str:
        """Helper to return mock text for testing/local environments based on filename."""
        fn_lower = filename.lower()
        if "biology" in fn_lower or "photosynthesis" in fn_lower:
            return (
                "Q1: A\n"
                "Q2: C\n"
                "Q3: Mitochondria is the powerhouse of the cell. It generates energy in the form of ATP "
                "through cellular respiration. It has a double membrane structure with its own DNA.\n"
                "Q4: Photosynthesis is the process used by plants to convert light energy into chemical energy. "
                "It takes place in the chloroplasts. Carbon dioxide and water are reacted using solar energy to "
                "produce glucose and oxygen. Light reactions occur in the thylakoid, and Dark reactions (Calvin cycle) "
                "take place in the stroma. This is the foundation of energy flow in almost all ecosystems."
            )
        elif "history" in fn_lower:
            return (
                "Q1: B\n"
                "Q2: D\n"
                "Q3: The French Revolution started in 1789 because of economic crisis, high taxation on the poor third estate, "
                "and the lavish lifestyle of King Louis XVI and Marie Antoinette. People wanted equality and freedom.\n"
                "Q4: The Industrial Revolution began in Great Britain during the 18th century due to abundant coal resources, "
                "technological innovations like the steam engine, and a stable political environment. It shifted agricultural societies "
                "into urban industrial hubs, fundamentally restructuring global labor, trade, and standard of living."
            )
        else:
            return (
                "Q1: C\n"
                "Q2: B\n"
                "Q3: Photosynthesis happens in green leaves where chlorophyll captures sunlight to synthesize glucose.\n"
                "Q4: The ecosystem is a community of living organisms interacting with non-living components. "
                "It maintains ecological balance through energy transfers and nutrient recycling systems."
            )
