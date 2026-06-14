import asyncio
import logging
import sys
from pathlib import Path
from typing import List

import click

from scorepilot.config import load_config
from scorepilot.scrapers import AQAScraper, CBSEScraper, PDFDownloader
from scorepilot.processors import PipelineOrchestrator, DatasetWriter, CBSEQuestionsMatcher


def setup_logging(log_dir: Path) -> None:
    """Configures logging for console and file output."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "scorepilot.log"

    # Set up root logger
    root_logger = logging.getLogger("scorepilot")
    root_logger.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logger = logging.getLogger("scorepilot.main")
    logger.info("Logging initialized. Output saved to %s", log_file)


@click.group()
@click.option("--config-path", type=click.Path(exists=True), help="Path to config.yaml file.")
@click.pass_context
def cli(ctx: click.Context, config_path: str) -> None:
    """ScorePilot Dataset Pipeline Command Line Interface."""
    # Load configuration
    config = load_config(config_path)
    ctx.obj = config
    setup_logging(config.paths.log_dir)


@cli.command()
@click.pass_obj
def init(config: Any) -> None:
    """Initialize the pipeline directories."""
    click.echo("Initializing directory structure...")
    config.setup_directories()
    click.echo(f"Raw data path: {config.paths.raw_dir}")
    click.echo(f"Processed path: {config.paths.processed_dir}")
    click.echo(f"Training path: {config.paths.training_dir}")
    click.echo(f"Logs path: {config.paths.log_dir}")
    click.echo("Success: Directory structure initialized.")


@cli.command()
@click.option("--board", type=click.Choice(["AQA", "CBSE"], case_sensitive=False), required=True, help="Exam board to scrape.")
@click.option("--subject", required=True, help="Subject (e.g. mathematics, chemistry).")
@click.option("--level", required=True, help="Exam level (e.g. gcse, class-10).")
@click.option("--year", type=int, required=True, help="Year to scrape.")
@click.pass_obj
def scrape(config: Any, board: str, subject: str, level: str, year: int) -> None:
    """Discovers papers on board portals (Dry run - does not download)."""
    click.echo(f"Searching papers for {board} {subject} {level} {year}...")
    
    if board.upper() == "AQA":
        scraper = AQAScraper(config)
    else:
        scraper = CBSEScraper(config)
        
    papers = scraper.discover_papers(subject=subject, level=level, year=year)
    
    click.echo(f"\nDiscovered {len(papers)} documents:")
    for idx, paper in enumerate(papers, 1):
        click.echo(f"{idx}. [{paper['doc_type'].upper()}] Code: {paper['paper_code'] or 'N/A'} -> {paper['download_url']}")
        
    click.echo("\nRun 'download' command to fetch files after discovery configuration.")


@cli.command()
@click.option("--url", required=True, help="Direct URL to PDF to download.")
@click.option("--board", type=click.Choice(["AQA", "CBSE"], case_sensitive=False), required=True)
@click.option("--doc-type", type=click.Choice(["question_paper", "mark_scheme"]), required=True)
@click.option("--filename", required=True, help="Target file name.")
@click.pass_obj
def download_single(config: Any, url: str, board: str, doc_type: str, filename: str) -> None:
    """Download a single exam paper PDF directly."""
    downloader = PDFDownloader(config)
    queue = [{
        "board": board,
        "doc_type": doc_type,
        "download_url": url,
        "file_name": filename
    }]
    
    click.echo(f"Downloading {url}...")
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(downloader.download_all(queue))
    
    if results and results[0][1]:
        click.echo("Download successful.")
    else:
        click.echo("Download failed.")


@cli.command()
@click.option("--qp", type=click.Path(exists=True), required=True, help="Path to Question Paper PDF.")
@click.option("--ms", type=click.Path(exists=True), required=True, help="Path to Mark Scheme PDF.")
@click.option("--board", type=click.Choice(["AQA", "CBSE"], case_sensitive=False), required=True)
@click.option("--subject", required=True)
@click.option("--level", required=True)
@click.option("--year", type=int, required=True)
@click.option("--code", help="Paper code.")
@click.pass_obj
def process_pair(
    config: Any, qp: str, ms: str, board: str, subject: str, level: str, year: int, code: str
) -> None:
    """Parses and merges a local Question Paper and Mark Scheme pair."""
    orchestrator = PipelineOrchestrator(config)
    writer = DatasetWriter(config)
    
    click.echo("Starting paper ingestion and processing...")
    success, merged_data, error = orchestrator.process_pair(
        qp_pdf_path=Path(qp),
        ms_pdf_path=Path(ms),
        subject=subject,
        level=level,
        year=year,
        board=board.upper(),
        paper_code=code
    )
    
    if success and merged_data:
        out_path = writer.save_processed_paper(merged_data)
        click.echo(f"Success! Processed paper saved to {out_path}")
        click.echo(f"Parsed {len(merged_data.pairs)} question-answer pairs.")
    else:
        click.echo(f"Processing failed: {error}")
        sys.exit(1)


@cli.command()
@click.option("--paper-ids", required=True, help="Comma-separated paper IDs to compile.")
@click.option("--output", required=True, help="Output file name inside training/ directory.")
@click.option("--format", type=click.Choice(["json", "jsonl"]), default="jsonl", help="Export format.")
@click.pass_obj
def compile_dataset(config: Any, paper_ids: str, output: str, format: str) -> None:
    """Compiles multiple parsed JSON paper files into a single training set."""
    writer = DatasetWriter(config)
    ids_list = [p.strip() for p in paper_ids.split(",") if p.strip()]
    
    click.echo(f"Compiling training dataset for papers: {ids_list}...")
    try:
        out_path = writer.compile_training_dataset(
            paper_ids=ids_list,
            output_filename=output,
            export_format=format
        )
        click.echo(f"Success! Compiled training dataset saved to {out_path}")
    except Exception as e:
        click.echo(f"Compilation failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--qp", type=click.Path(exists=True), help="Path to extracted questions JSON.")
@click.option("--ms", type=click.Path(exists=True), help="Path to extracted mark schemes JSON.")
@click.option("--output", type=click.Path(), help="Path to save matched output JSON.")
@click.pass_obj
def match_cbse(config: Any, qp: str, ms: str, output: str) -> None:
    """Aligns extracted CBSE Class 12 questions with their mark schemes."""
    matcher = CBSEQuestionsMatcher(config)
    
    qp_path = Path(qp) if qp else config.paths.processed_dir / "cbse_extracted_samples.json"
    ms_path = Path(ms) if ms else config.paths.processed_dir / "cbse_ms_samples.json"
    output_path = Path(output) if output else config.paths.processed_dir / "cbse_questions.json"
    
    click.echo(f"Aligning CBSE questions and mark schemes...")
    click.echo(f"QP Source: {qp_path}")
    click.echo(f"MS Source: {ms_path}")
    click.echo(f"Output: {output_path}")
    
    try:
        stats = matcher.match_cbse_dataset(
            qp_file_path=qp_path,
            ms_file_path=ms_path,
            output_file_path=output_path
        )
        
        click.echo("\n==================================================")
        click.echo("CBSE Question-Answer Match Alignment Statistics")
        click.echo("==================================================")
        
        total_matched = 0
        for subj, subj_stats in stats.items():
            click.echo(f"\nSubject: {subj}")
            click.echo(f"- Total linked questions     : {subj_stats['total_linked']}")
            click.echo(f"- Unmatched paper questions  : {len(subj_stats['unmatched_paper'])}")
            if subj_stats['unmatched_paper']:
                click.echo(f"  Labels: {subj_stats['unmatched_paper']}")
            click.echo(f"- Unmatched mark scheme items: {len(subj_stats['unmatched_mark_scheme'])}")
            if subj_stats['unmatched_mark_scheme']:
                click.echo(f"  Labels: {subj_stats['unmatched_mark_scheme']}")
            click.echo(f"- Match Accuracy Estimate    : {subj_stats['accuracy_estimate']:.1f}%")
            total_matched += subj_stats['total_linked']
            
        click.echo("\n--------------------------------------------------")
        click.echo(f"Saved {total_matched} total matched question-answer pairs to: {output_path}")
        click.echo("==================================================")
        
    except Exception as e:
        click.echo(f"CBSE Matching failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--limit", type=int, default=100, help="Maximum number of PDFs to download (for politeness).")
@click.pass_obj
def discover_aqa(config: Any, limit: int) -> None:
    """Discovers and downloads AQA past exam papers and mark schemes."""
    import json
    scraper = AQAScraper(config)
    downloader = PDFDownloader(config)
    
    click.echo("Discovering all AQA past papers and mark schemes...")
    discovered = scraper.discover_all_papers()
    
    if not discovered:
        click.echo("No papers discovered.")
        return
        
    subjects_found = sorted(list(set(p["subject"] for p in discovered)))
    years_found = sorted(list(set(p["year"] for p in discovered)))
    
    click.echo(f"Discovered {len(discovered)} total documents across AQA.")
    click.echo(f"Subjects: {', '.join(subjects_found)}")
    click.echo(f"Years: {', '.join(map(str, years_found))}")
    
    # Filter recent papers (e.g. 2023, 2024) to download
    download_queue = [p for p in discovered if p["year"] in [2023, 2024]]
    if len(download_queue) > limit:
        click.echo(f"Limiting download queue to {limit} papers for politeness...")
        download_queue = download_queue[:limit]
        
    click.echo(f"Downloading {len(download_queue)} queued PDFs...")
    
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(downloader.download_all(download_queue))
    
    downloaded_count = sum(1 for _, success in results if success)
    failed_count = len(results) - downloaded_count
    
    # Generate manifest
    downloaded_urls = {item["download_url"] for item, success in results if success}
    manifest_items = []
    for p in discovered:
        manifest_items.append({
            "subject": p["subject"],
            "level": p["level"],
            "year": p["year"],
            "doc_type": p["doc_type"],
            "title": p["title"],
            "download_url": p["download_url"],
            "file_name": p["file_name"],
            "downloaded": p["download_url"] in downloaded_urls
        })
        
    manifest_path = config.paths.raw_dir / "aqa" / "aqa_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_items, f, indent=2, ensure_ascii=False)
        
    click.echo("\n==================================================")
    click.echo("AQA Discovery and Download Summary")
    click.echo("==================================================")
    click.echo(f"- Subjects found   : {len(subjects_found)} ({', '.join(subjects_found)})")
    click.echo(f"- Years found      : {len(years_found)} ({', '.join(map(str, years_found))})")
    click.echo(f"- PDFs downloaded  : {downloaded_count}")
    click.echo(f"- Failed downloads : {failed_count}")
    click.echo(f"- Manifest saved to: {manifest_path}")
    click.echo("==================================================")


if __name__ == "__main__":
    cli()
