import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import requests
from scorepilot.config import Config

logger = logging.getLogger("scorepilot.scrapers.base")


class BaseScraper(ABC):
    """Abstract base class for exam board scrapers."""

    def __init__(self, config: Config, board_name: str):
        self.config = config
        self.board_name = board_name
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.config.scrapers.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self._last_request_time = 0.0

    def _wait_for_rate_limit(self) -> None:
        """Throttles requests to avoid overloading target servers."""
        elapsed = time.time() - self._last_request_time
        delay = self.config.scrapers.rate_limit_delay
        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug(f"Throttling scraper: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def get_html(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Fetch HTML content from a URL safely with retries."""
        self._wait_for_rate_limit()
        
        max_retries = self.config.scrapers.max_retries
        backoff = self.config.scrapers.backoff_factor
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Fetching: {url} (Attempt {attempt}/{max_retries})")
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.config.scrapers.request_timeout
                )
                
                if response.status_code == 200:
                    return response.text
                
                logger.warning(
                    f"HTTP {response.status_code} received from {url}. Retrying..."
                )
                
            except requests.RequestException as e:
                logger.warning(f"Connection failure on {url}: {e}. Retrying...")
                
            time.sleep(backoff ** attempt)
            
        logger.error(f"Failed to fetch HTML from {url} after {max_retries} attempts.")
        return None

    @abstractmethod
    def discover_papers(self, subject: str, level: str, year: int) -> List[Dict[str, Any]]:
        """Scrape paper references and return list of document metadata.
        
        Structure of output dict:
        {
            "board": str,
            "subject": str,
            "level": str,
            "year": int,
            "paper_code": Optional[str],
            "doc_type": "question_paper" | "mark_scheme",
            "download_url": str,
            "file_name": str
        }
        """
        pass
