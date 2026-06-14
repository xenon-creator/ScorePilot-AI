import logging
import io
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image

# Third-party layout libraries
import fitz  # PyMuPDF
import pdfplumber

from scorepilot.config import Config

# Safe import for PaddleOCR
try:
    from paddleocr import PaddleOCR
    import numpy as np
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    np = None  # type: ignore
    PaddleOCR = None  # type: ignore

logger = logging.getLogger("scorepilot.parsers.pdf_engine")


class ParsedPage:
    """Dataclass representing raw parsed content from a single PDF page."""
    def __init__(
        self,
        page_number: int,
        text: str,
        tables: List[List[List[Optional[str]]]],
        extraction_method: str,
        images: List[Dict[str, Any]],
        raw_page_ref: Any = None
    ):
        self.page_number = page_number
        self.text = text
        self.tables = tables
        self.extraction_method = extraction_method  # "pymupdf", "pdfplumber", or "paddleocr"
        self.images = images
        self.raw_page_ref = raw_page_ref  # Reference to fitz.Page or pdfplumber.Page


class ParsedDocument:
    """Object enclosing a parsed PDF containing all its structured pages."""
    def __init__(self, file_path: Path, pages: List[ParsedPage]):
        self.file_path = file_path
        self.pages = pages
        self.metadata: Dict[str, Any] = {}

    @property
    def full_text(self) -> str:
        """Concatenated text from all parsed pages."""
        return "\n\n".join(f"--- Page {p.page_number} ---\n{p.text}" for p in self.pages)


class PDFParserEngine:
    """Unified PDF extraction engine utilizing PyMuPDF, pdfplumber, and PaddleOCR fallbacks."""
    
    def __init__(self, config: Config):
        self.config = config
        self.ocr_engine: Optional[Any] = None
        self._init_ocr()

    def _init_ocr(self) -> None:
        """Dynamically initialize PaddleOCR if enabled in config and installed."""
        if not self.config.parsers.ocr_enabled:
            logger.info("PaddleOCR is disabled by config.")
            return

        if not PADDLEOCR_AVAILABLE:
            logger.warning(
                "paddleocr or dependencies (paddlepaddle/numpy) are not installed in the current environment. "
                "OCR fallback will write warning logs and return placeholder strings instead of failing."
            )
            return

        try:
            # Initialize PaddleOCR engine (runs download of default English weights on first run)
            # lang='en' is default. We set show_log=False to keep terminal logs clean.
            self.ocr_engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            logger.info("PaddleOCR engine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR engine: {e}. OCR fallback will be disabled.")
            self.ocr_engine = None

    def parse_pdf(self, pdf_path: Path) -> ParsedDocument:
        """Parses a PDF using the primary extraction mechanisms and fallback if necessary.
        
        Args:
            pdf_path: Absolute path to the PDF file.
            
        Returns:
            ParsedDocument containing all pages and metadata.
        """
        logger.info(f"Starting PDF parsing: {pdf_path}")
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

        parsed_pages: List[ParsedPage] = []
        
        # 1. Open with PyMuPDF for fast parsing and layout check
        doc_fitz = fitz.open(str(pdf_path))
        
        # 2. Open with pdfplumber for high-quality table extraction
        # We wrap in try-except block to handle corrupted PDFs or pdfplumber issues
        try:
            doc_plumber = pdfplumber.open(str(pdf_path))
        except Exception as e:
            logger.error(f"pdfplumber failed to open PDF {pdf_path}: {e}. Falling back to PyMuPDF only.")
            doc_plumber = None

        for page_idx in range(len(doc_fitz)):
            page_num = page_idx + 1
            page_fitz = doc_fitz[page_idx]
            page_plumber = doc_plumber.pages[page_idx] if doc_plumber else None
            
            # A. Extract text using PyMuPDF (fast, robust text/layout)
            text = page_fitz.get_text("text").strip()
            extraction_method = "pymupdf"
            
            # B. Extract tables using pdfplumber if enabled
            tables: List[List[List[Optional[str]]]] = []
            if self.config.parsers.extract_tables and page_plumber:
                try:
                    # pdfplumber table returns list of lists of strings
                    raw_tables = page_plumber.extract_tables()
                    if raw_tables:
                        tables = raw_tables
                        logger.debug(f"Extracted {len(tables)} tables from page {page_num}")
                except Exception as e:
                    logger.warning(f"Failed to extract tables using pdfplumber on page {page_num}: {e}")

            # C. Detect scanned document / empty text and trigger OCR fallback
            # We trigger OCR if text is extremely short (e.g. less than 30 characters) but page is not empty
            if len(text) < 30:
                logger.info(f"Page {page_num} text content sparse ({len(text)} chars). Triggering OCR fallback...")
                ocr_text = self._run_ocr(page_fitz, page_num)
                if ocr_text:
                    text = ocr_text
                    extraction_method = "paddleocr"

            # D. Find inline images
            images: List[Dict[str, Any]] = []
            try:
                for img_info in page_fitz.get_images(full=True):
                    images.append({
                        "xref": img_info[0],
                        "width": img_info[2],
                        "height": img_info[3],
                        "ext": img_info[4],
                    })
            except Exception as e:
                logger.warning(f"Failed to extract image list on page {page_num}: {e}")

            parsed_pages.append(
                ParsedPage(
                    page_number=page_num,
                    text=text,
                    tables=tables,
                    extraction_method=extraction_method,
                    images=images,
                    raw_page_ref=page_fitz
                )
            )

        doc_fitz.close()
        if doc_plumber:
            doc_plumber.close()

        logger.info(f"Completed parsing PDF: {pdf_path}. Total pages: {len(parsed_pages)}")
        return ParsedDocument(pdf_path, parsed_pages)

    def _run_ocr(self, page_fitz: fitz.Page, page_num: int) -> str:
        """Renders page to image and runs PaddleOCR on it."""
        if not self.config.parsers.ocr_enabled:
            logger.info("OCR is disabled in settings. Skipping fallback.")
            return ""

        if self.ocr_engine is None:
            logger.warning(f"PaddleOCR engine is unavailable. Returning OCR placeholder for page {page_num}.")
            return f"[OCR Fallback triggered for Page {page_num}: PaddleOCR dependencies missing]"

        try:
            # Render page to Pixmap using configured DPI
            pix = page_fitz.get_pixmap(dpi=self.config.parsers.dpi)
            img_data = pix.tobytes("png")
            
            # Load into PIL Image then convert to numpy array for PaddleOCR
            image = Image.open(io.BytesIO(img_data)).convert("RGB")
            img_np = np.array(image)
            
            # Run PaddleOCR inference
            # result structure: [ [ [ [box_coords], (text, confidence) ], ... ] ]
            ocr_result = self.ocr_engine.ocr(img_np, cls=True)
            
            if not ocr_result or not ocr_result[0]:
                logger.info(f"OCR returned empty results for page {page_num}")
                return ""
            
            lines: List[str] = []
            for line in ocr_result[0]:
                box_info, (text, confidence) = line
                if confidence >= self.config.parsers.ocr_confidence_threshold:
                    lines.append(text)
                    
            logger.info(f"OCR extracted {len(lines)} lines from page {page_num}")
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to run OCR on page {page_num}: {e}")
            return f"[OCR Fallback error on Page {page_num}: {e}]"
