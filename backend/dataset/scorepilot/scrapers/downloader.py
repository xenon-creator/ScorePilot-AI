import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
import aiohttp
from tqdm.asyncio import tqdm
from scorepilot.config import Config

logger = logging.getLogger("scorepilot.scrapers.downloader")


class PDFDownloader:
    """Asynchronous PDF downloader with retries, politeness limiters, and file validation."""

    def __init__(self, config: Config):
        self.config = config
        self.semaphore = asyncio.Semaphore(self.config.scrapers.concurrency_limit)
        
    async def download_all(self, download_queue: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], bool]]:
        """Downloads all queued PDF papers concurrently.
        
        Args:
            download_queue: List of dictionaries matching discovered paper schemas.
            
        Returns:
            A list of tuples (paper_meta, success_status)
        """
        if not download_queue:
            logger.info("Download queue is empty.")
            return []

        logger.info(f"Initiating async download for {len(download_queue)} documents...")
        
        # Create output folders
        self.config.setup_directories()

        # Custom headers
        headers = {
            "User-Agent": self.config.scrapers.user_agent,
            "Accept": "application/pdf,application/octet-stream,*/*",
        }
        
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            tasks = [
                self._download_item(session, item)
                for item in download_queue
            ]
            
            # Use tqdm to show real-time progress
            results = await tqdm.gather(*tasks, desc="Downloading PDFs")
            
        success_count = sum(1 for _, success in results if success)
        logger.info(f"Downloads completed. Success: {success_count}/{len(download_queue)}")
        return results

    async def _download_item(self, session: aiohttp.ClientSession, item: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """Download a single item from the queue with rate limits and retries."""
        url = item["download_url"]
        board = item["board"].lower()
        doc_type = item["doc_type"]
        file_name = item["file_name"]
        
        # Resolve target storage path
        target_dir = self.config.paths.raw_dir / board
        dest_path = target_dir / file_name

        # Skip if already exists and is a valid PDF
        if dest_path.exists() and self._is_valid_pdf(dest_path):
            logger.debug(f"File already downloaded and valid: {dest_path.name}. Skipping.")
            return item, True

        max_retries = self.config.scrapers.max_retries
        backoff = self.config.scrapers.backoff_factor

        async with self.semaphore:
            # Politeness delay before starting request
            await asyncio.sleep(self.config.scrapers.rate_limit_delay)
            
            for attempt in range(1, max_retries + 1):
                try:
                    logger.debug(f"Downloading {url} (Attempt {attempt}/{max_retries})")
                    
                    async with session.get(url, timeout=self.config.scrapers.request_timeout) as response:
                        if response.status != 200:
                            logger.warning(
                                f"Failed HTTP {response.status} for {url}. Retrying..."
                            )
                            await asyncio.sleep(backoff ** attempt)
                            continue

                        # Ensure output directories exist
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Write file in chunks
                        with open(dest_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(1024 * 64):
                                f.write(chunk)
                                
                        # Validate file integrity
                        if self._is_valid_pdf(dest_path):
                            logger.info(f"Successfully downloaded: {dest_path.name}")
                            return item, True
                        else:
                            logger.error(
                                f"Downloaded file {dest_path.name} is corrupt or not a PDF. Retrying..."
                            )
                            if dest_path.exists():
                                dest_path.unlink()
                                
                except Exception as e:
                    logger.warning(f"Error downloading {url} on attempt {attempt}: {e}")
                    
                await asyncio.sleep(backoff ** attempt)

        logger.error(f"Permanently failed to download {url} after {max_retries} attempts.")
        return item, False

    def _is_valid_pdf(self, path: Path) -> bool:
        """Verifies if the downloaded file is a valid PDF checking the magic header."""
        if not path.exists() or path.stat().st_size < 4:
            return False
        try:
            with open(path, "rb") as f:
                header = f.read(4)
                return header == b"%PDF"
        except Exception:
            return False
