import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import aiohttp
from bs4 import BeautifulSoup

# Ensure package imports work by adding root path to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent.resolve()))

from scorepilot.config import load_config

# Set up logging for CBSE scraping script run
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("scorepilot.scrapers.cbse_runner")

CBSE_URL = "https://cbseacademic.nic.in/SQP_CLASSXII_2025-26.html"
BASE_URL = "https://cbseacademic.nic.in"


def get_subject_folder(token: str) -> str:
    """Standardizes subject tokens to folder names.
    
    Maps 'Maths' -> 'Mathematics' and capitalizes initial letters.
    """
    if token.lower() == "maths":
        return "Mathematics"
    if token[0].islower():
        token = token[0].upper() + token[1:]
    return token


def parse_cbse_page(html: str) -> List[Dict[str, Any]]:
    """Parses HTML content, extracts all PDF links, and groups SQPs and MSs by subject."""
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    
    pdf_links = []
    for link in links:
        href = link["href"].strip()
        if href.endswith(".pdf"):
            text = link.get_text().strip()
            # Normalize to absolute URL
            if not href.startswith("http"):
                if href.startswith("/"):
                    absolute_url = f"{BASE_URL}{href}"
                else:
                    absolute_url = f"{BASE_URL}/{href}"
            else:
                absolute_url = href
                
            pdf_links.append({
                "text": text,
                "url": absolute_url,
                "filename": absolute_url.split("/")[-1]
            })

    # Group by subject and lang
    # Regex: captures subject token, type (SQP/MS), and lang suffix (_hi)
    pattern = re.compile(r'^([A-Za-z0-9_\-]+?)[-_](SQP|MS)(_hi)?\.pdf$', re.IGNORECASE)
    
    grouped_subjects: Dict[str, Dict[str, Any]] = {}
    
    for p in pdf_links:
        filename = p["filename"]
        match = pattern.match(filename)
        if not match:
            logger.warning(f"Unmatched PDF filename layout: {filename}. Skipping.")
            continue
            
        token = match.group(1)
        doc_type = match.group(2).upper()
        is_hindi = bool(match.group(3))
        
        subject_folder = get_subject_folder(token)
        
        # Manifest subject name format
        subject_name = f"{subject_folder} (Hindi)" if is_hindi else subject_folder
        
        if subject_name not in grouped_subjects:
            grouped_subjects[subject_name] = {
                "subject": subject_name,
                "folder": subject_folder,
                "paper_url": None,
                "mark_scheme_url": None,
                "paper_filename": None,
                "mark_scheme_filename": None
            }
            
        if doc_type == "SQP":
            grouped_subjects[subject_name]["paper_url"] = p["url"]
            grouped_subjects[subject_name]["paper_filename"] = filename
        elif doc_type == "MS":
            grouped_subjects[subject_name]["mark_scheme_url"] = p["url"]
            grouped_subjects[subject_name]["mark_scheme_filename"] = filename

    return list(grouped_subjects.values())


def is_valid_pdf(path: Path) -> bool:
    """Verifies file exists and has %PDF magic header."""
    if not path.exists() or path.stat().st_size < 4:
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(4)
            return header == b"%PDF"
    except Exception:
        return False


async def download_file(
    session: aiohttp.ClientSession,
    url: str,
    dest_path: Path,
    max_retries: int,
    backoff: float,
    rate_limit_delay: float,
    semaphore: asyncio.Semaphore
) -> bool:
    """Downloads a single file asynchronously with rate-limiting, retries, and validation."""
    if is_valid_pdf(dest_path):
        logger.info(f"File already downloaded and valid: {dest_path.name}")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    async with semaphore:
        await asyncio.sleep(rate_limit_delay)
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Downloading {dest_path.name} (Attempt {attempt}/{max_retries})")
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(dest_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(65536):
                                f.write(chunk)
                                
                        if is_valid_pdf(dest_path):
                            logger.info(f"Successfully downloaded: {dest_path.name}")
                            return True
                        else:
                            logger.error(f"Downloaded file {dest_path.name} has invalid PDF header.")
                            if dest_path.exists():
                                dest_path.unlink()
                    else:
                        logger.warning(f"HTTP {response.status} downloading {dest_path.name}")
            except Exception as e:
                logger.warning(f"Error downloading {dest_path.name} (Attempt {attempt}): {e}")
                
            await asyncio.sleep(backoff ** attempt)
            
    logger.error(f"Failed to download {dest_path.name} after {max_retries} attempts.")
    return False


async def run_scraper() -> None:
    # 1. Load pipeline configuration
    config = load_config()
    raw_cbse_dir = config.paths.raw_dir / "cbse"
    raw_cbse_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Fetch page HTML
    logger.info(f"Fetching CBSE Academic portal: {CBSE_URL}")
    async with aiohttp.ClientSession() as session:
        async with session.get(CBSE_URL) as response:
            if response.status != 200:
                logger.critical(f"Failed to fetch CBSE page. Status: {response.status}")
                return
            html = await response.text()

    # 3. Parse and group subjects
    grouped_papers = parse_cbse_page(html)
    logger.info(f"Discovered {len(grouped_papers)} distinct subject papers/variations.")

    # 4. Initiate download queue
    concurrency_limit = config.scrapers.concurrency_limit
    max_retries = config.scrapers.max_retries
    backoff = config.scrapers.backoff_factor
    delay = config.scrapers.rate_limit_delay
    
    semaphore = asyncio.Semaphore(concurrency_limit)
    headers = {"User-Agent": config.scrapers.user_agent}

    # Track download manifest items
    manifest: List[Dict[str, Any]] = []
    download_tasks = []
    
    # To run downloads concurrently, we register tasks
    async with aiohttp.ClientSession(headers=headers) as session:
        for idx, paper in enumerate(grouped_papers):
            subj_name = paper["subject"]
            subj_folder = paper["folder"]
            subject_target_dir = raw_cbse_dir / subj_folder
            
            paper_url = paper["paper_url"]
            ms_url = paper["mark_scheme_url"]
            
            paper_file = paper["paper_filename"]
            ms_file = paper["mark_scheme_filename"]

            task_meta = {
                "subject": subj_name,
                "folder": subj_folder,
                "paper_url": paper_url,
                "ms_url": ms_url,
                "paper_file": paper_file,
                "ms_file": ms_file,
                "paper_dest_rel": f"{subj_folder}/{paper_file}" if paper_file else None,
                "ms_dest_rel": f"{subj_folder}/{ms_file}" if ms_file else None,
                "paper_success": False,
                "ms_success": False
            }
            manifest.append(task_meta)

            # Enqueue downloads
            if paper_url and paper_file:
                dest = subject_target_dir / paper_file
                task = download_file(session, paper_url, dest, max_retries, backoff, delay, semaphore)
                download_tasks.append((idx, "paper", task))
                
            if ms_url and ms_file:
                dest = subject_target_dir / ms_file
                task = download_file(session, ms_url, dest, max_retries, backoff, delay, semaphore)
                download_tasks.append((idx, "ms", task))

        logger.info(f"Starting execution of {len(download_tasks)} PDF downloads...")
        
        # Gather all tasks
        indices_types, tasks = zip(*[( (idx, dtype), task ) for idx, dtype, task in download_tasks])
        results = await asyncio.gather(*tasks)

        # Map results back to manifest
        for (idx, dtype), success in zip(indices_types, results):
            if dtype == "paper":
                manifest[idx]["paper_success"] = success
            elif dtype == "ms":
                manifest[idx]["ms_success"] = success

    # 5. Format and save final manifest
    final_manifest = []
    downloaded_count = 0
    failed_downloads = []

    for item in manifest:
        paper_success = item["paper_success"] or (item["paper_url"] is None)
        ms_success = item["ms_success"] or (item["mark_url"] is None if "mark_url" in item else item["ms_url"] is None)
        
        # Check download status
        both_success = item["paper_success"] and item["ms_success"]
        
        if item["paper_url"] and item["paper_success"]:
            downloaded_count += 1
        elif item["paper_url"]:
            failed_downloads.append(f"{item['subject']} - Paper: {item['paper_url']}")
            
        if item["ms_url"] and item["ms_success"]:
            downloaded_count += 1
        elif item["ms_url"]:
            failed_downloads.append(f"{item['subject']} - Mark Scheme: {item['ms_url']}")

        final_manifest.append({
            "subject": item["subject"],
            "paper_pdf": item["paper_dest_rel"] or "",
            "mark_scheme_pdf": item["ms_dest_rel"] or "",
            "downloaded": both_success
        })

    manifest_path = raw_cbse_dir / "download_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(final_manifest, f, indent=2, ensure_ascii=False)

    logger.info("Manifest generated and saved.")
    print("--------------------------------------------------")
    print(f"Subjects/Variations Found : {len(grouped_papers)}")
    print(f"Total PDFs Downloaded      : {downloaded_count}")
    print(f"Failed Downloads           : {len(failed_downloads)}")
    print("--------------------------------------------------")
    if failed_downloads:
        print("Failed Details:")
        for failed in failed_downloads:
            print(f"- {failed}")
    else:
        print("All downloads completed successfully without errors.")


if __name__ == "__main__":
    asyncio.run(run_scraper())
