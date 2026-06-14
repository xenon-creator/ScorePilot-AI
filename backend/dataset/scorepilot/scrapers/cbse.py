import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from scorepilot.config import Config
from scorepilot.scrapers.base import BaseScraper

logger = logging.getLogger("scorepilot.scrapers.cbse")


class CBSEScraper(BaseScraper):
    """Scraper implementation for CBSE past exam papers and marking schemes."""

    def __init__(self, config: Config):
        super().__init__(config, board_name="CBSE")
        self.base_url = "https://www.cbse.gov.in"
        self.academic_url = "https://cbseacademic.nic.in"

    def discover_papers(self, subject: str, level: str, year: int) -> List[Dict[str, Any]]:
        """Queries CBSE portal for past papers based on target subject, year, and class level.
        
        Args:
            subject: e.g. "mathematics", "science"
            level: e.g. "class-10", "class-12" (or "class x", "class xii")
            year: e.g. 2023
            
        Returns:
            A list of dictionary metadata mappings.
        """
        logger.info(f"Discovering CBSE papers for Subject: {subject}, Level: {level}, Year: {year}")
        
        # CBSE hosts links on academic page structures e.g. SQP_CLASSX_2023_24.html
        # We target both standard new archive portal and academic portal links
        class_label = "CLASSX" if "10" in level or "x" in level.lower() else "CLASSXII"
        target_path = f"/SQP_{class_label}_{year}_{str(year+1)[2:]}.html"
        
        # Use academic URL for sample papers, or main portal for actual exams
        url = f"{self.academic_url}{target_path}"
        
        html_content = self.get_html(url)
        if not html_content:
            # Fallback to main question-paper portal archive URL
            archive_url = f"{self.base_url}/cbsenew/question-paper.html"
            logger.info(f"SQP page not found. Querying general archive index: {archive_url}")
            html_content = self.get_html(archive_url)
            if not html_content:
                logger.warning(f"Failed to access CBSE listings.")
                return []

        papers = self._parse_cbse_listings(html_content, subject, level, year)
        logger.info(f"Discovered {len(papers)} papers on CBSE.")
        return papers

    def _parse_cbse_listings(
        self, html: str, subject: str, level: str, year: int
    ) -> List[Dict[str, Any]]:
        """Parses CBSE listing page to locate subject-specific PDF downloads."""
        soup = BeautifulSoup(html, "lxml")
        discovered: List[Dict[str, Any]] = []

        # CBSE past papers typically map subject names in a table row:
        # Row layout: [Subject Name] | [Question Paper PDF Link] | [Marking Scheme PDF Link]
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            
            row_text = "".join(c.get_text() for c in cells).lower()
            
            # Check if this row matches our subject
            if subject.lower() not in row_text:
                continue

            # Process links in this matched row
            for cell_idx, cell in enumerate(cells):
                links = cell.find_all("a", href=True)
                for link in links:
                    href = link["href"]
                    text = link.get_text().strip().lower()
                    
                    is_pdf = href.endswith(".pdf")
                    if not is_pdf:
                        continue
                    
                    # Resolve full URL
                    download_url = href
                    if href.startswith("/"):
                        download_url = f"{self.academic_url}{href}"
                    elif not href.startswith("http"):
                        download_url = f"{self.academic_url}/{href}"

                    # Determine if it's Question Paper or MS/Answer Key
                    # Column positioning or anchor text contains indicators
                    is_ms = "ms" in text or "marking" in text or "scheme" in text or "ans" in text or "key" in text
                    # Often the marking schemes are in column 2, papers in column 1
                    if not is_ms and cell_idx > 1:
                        is_ms = True

                    doc_type = "mark_scheme" if is_ms else "question_paper"
                    file_name = f"cbse_{subject}_{level}_{year}_{doc_type}.pdf".lower().replace(" ", "_")

                    discovered.append({
                        "board": "CBSE",
                        "subject": subject,
                        "level": level,
                        "year": year,
                        "paper_code": None,
                        "doc_type": doc_type,
                        "download_url": download_url,
                        "file_name": file_name
                    })

        return discovered
