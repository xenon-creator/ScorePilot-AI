import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from scorepilot.config import Config
from scorepilot.scrapers.base import BaseScraper

logger = logging.getLogger("scorepilot.scrapers.aqa")


class AQAScraper(BaseScraper):
    """Scraper implementation for AQA past exam papers and mark schemes."""

    SUBJECT_URLS = {
        "biology": {
            "gcse": "https://www.aqa.org.uk/subjects/science/gcse/biology-8461/assessment-resources",
            "a-level": "https://www.aqa.org.uk/subjects/biology/a-level/biology-7402/assessment-resources"
        },
        "chemistry": {
            "gcse": "https://www.aqa.org.uk/subjects/science/gcse/chemistry-8462/assessment-resources",
            "a-level": "https://www.aqa.org.uk/subjects/chemistry/a-level/chemistry-7405/assessment-resources"
        },
        "physics": {
            "gcse": "https://www.aqa.org.uk/subjects/science/gcse/physics-8463/assessment-resources",
            "a-level": "https://www.aqa.org.uk/subjects/physics/a-level/physics-7408/assessment-resources"
        },
        "mathematics": {
            "gcse": "https://www.aqa.org.uk/subjects/mathematics/gcse/mathematics-8300/assessment-resources",
            "a-level": "https://www.aqa.org.uk/subjects/mathematics/as-and-a-level/mathematics-7357/assessment-resources"
        }
    }

    def __init__(self, config: Config):
        super().__init__(config, board_name="AQA")
        self.base_url = "https://www.aqa.org.uk"

    def discover_papers(self, subject: str, level: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Queries the AQA past paper search results for documents.
        
        Args:
            subject: e.g. "mathematics", "biology"
            level: e.g. "gcse", "a-level"
            year: Optional year limit.
            
        Returns:
            A list of dictionary metadata mappings.
        """
        subj_key = subject.strip().lower()
        level_key = level.strip().lower()

        if subj_key not in self.SUBJECT_URLS:
            logger.error(f"Subject '{subject}' is not supported by AQA scraper.")
            return []
        if level_key not in self.SUBJECT_URLS[subj_key]:
            logger.error(f"Level '{level}' is not supported for subject '{subject}'.")
            return []

        url = self.SUBJECT_URLS[subj_key][level_key]
        html_content = self.get_html(url)
        if not html_content:
            logger.warning(f"Could not retrieve assessment resources page for AQA {subject} {level}")
            return []

        papers = self._parse_sanity_payload(html_content, subject, level)
        
        if year is not None:
            # Filter by specific year
            papers = [p for p in papers if p["year"] == year]

        logger.info(f"Discovered {len(papers)} papers on AQA for {subject} {level} (year={year}).")
        return papers

    def discover_all_papers(self) -> List[Dict[str, Any]]:
        """Crawls all configured AQA subject and level resources pages to discover all available papers."""
        all_papers = []
        for subject, levels in self.SUBJECT_URLS.items():
            for level in levels.keys():
                # Map to proper display names
                display_subj = subject.capitalize()
                display_level = "gcse" if level == "gcse" else "a-level"
                papers = self.discover_papers(display_subj, display_level)
                all_papers.extend(papers)
        return all_papers

    def _parse_sanity_payload(self, html: str, subject: str, level: str) -> List[Dict[str, Any]]:
        """Extracts PDF urls and metadata from Next.js sanity payload."""
        url_pattern = re.compile(r'https://cdn.sanity.io/files/[a-zA-Z0-9\-\.\/_]+\.pdf')
        matches = list(url_pattern.finditer(html))
        
        discovered: List[Dict[str, Any]] = []
        seen_urls = set()

        for match in matches:
            pdf_url = match.group(0)
            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)

            # Extract window around match to extract title and metadata
            pos = match.start()
            start = max(0, pos - 2000)
            end = min(len(html), pos + 2000)
            chunk = html[start:end].replace('\\"', '"').replace('\\\\', '\\')

            title_match = re.search(r'"title"\s*:\s*"([^"]+)"', chunk)
            fn_match = re.search(r'"originalFilename"\s*:\s*"([^"]+)"', chunk)

            title = title_match.group(1) if title_match else ""
            filename = fn_match.group(1) if fn_match else ""

            if not title and not filename:
                continue

            title_lower = title.lower()
            filename_lower = filename.lower()

            # Identify if it is a question paper or mark scheme
            is_qp = "question paper" in title_lower or "-qp-" in filename_lower or "qp" in filename_lower or "sqp" in filename_lower
            is_ms = "mark scheme" in title_lower or "-ms-" in filename_lower or "ms" in filename_lower or "sms" in filename_lower

            if not is_qp and not is_ms:
                continue

            doc_type = "question_paper" if is_qp else "mark_scheme"

            # Check exclusions (e.g. examiner reports, inserts, specifications)
            exclude_keywords = ["report", "guidance", "declaration", "descriptor", "specification", "flyer", "insert", "confidential"]
            if any(kw in title_lower or kw in filename_lower for kw in exclude_keywords):
                continue

            # Skip modified papers
            if "modified" in title_lower or "modified" in filename_lower:
                continue

            # Extract year
            pub_year = self._extract_year(title, filename)
            if not pub_year:
                pub_year = 2024  # Specimen papers / default fallback

            # Generate target filename
            file_name = f"aqa_{subject.lower()}_{level}_{pub_year}_{doc_type}"
            
            # Extract paper code/suffix (e.g. 1F, 1H, 2, 3)
            paper_suffix = ""
            p_match = re.search(r'paper\s*([0-9][a-z]?)\b', title, re.IGNORECASE)
            if p_match:
                paper_suffix = p_match.group(1).lower()
            else:
                p_match = re.search(r'8461([0-9][a-z]?)\b', filename, re.IGNORECASE)
                if p_match:
                    paper_suffix = p_match.group(1).lower()

            if paper_suffix:
                file_name += f"_{paper_suffix}"
            file_name += ".pdf"

            discovered.append({
                "board": "AQA",
                "subject": subject,
                "level": level,
                "year": pub_year,
                "doc_type": doc_type,
                "download_url": pdf_url,
                "file_name": file_name.lower(),
                "title": title
            })

        return discovered

    def _extract_year(self, title: str, filename: str) -> Optional[int]:
        """Extracts 4-digit years or 2-digit years with month prefixes."""
        for text in [title, filename]:
            match = re.search(r'\b(20[0-9]{2})\b', text)
            if match:
                return int(match.group(1))
        for text in [title, filename]:
            match = re.search(r'\b(jun|nov|dec|jan|feb|mar|apr|may|jul|aug|sep|oct)([0-9]{2})\b', text, re.IGNORECASE)
            if match:
                return 2000 + int(match.group(2))
            match = re.search(r'-(jun|nov|dec|jan|feb|mar|apr|may|jul|aug|sep|oct)([0-9]{2})\b', text, re.IGNORECASE)
            if match:
                return 2000 + int(match.group(2))
        return None
