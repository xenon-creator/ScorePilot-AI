# ScorePilot Dataset Pipeline

ScorePilot is a production-grade dataset engineering pipeline designed to ingest and parse school examination papers (questions and mark schemes) from CBSE and AQA, validating them using strict schemas, and outputting structured datasets ready for training AI models.

## Project Structure

```text
scorepilot/
├── scrapers/            # Asynchronous crawler and downloader modules
├── parsers/             # Multi-engine PDF layout parser (PyMuPDF, pdfplumber, PaddleOCR)
├── processors/          # Pipeline management, matching and orchestration
├── validators/          # Pydantic schemas and pipeline data validation models
├── datasets/            # File-based database structure
│   ├── raw/             # Unprocessed scraped HTML page data and downloaded PDF files
│   │   ├── cbse/
│   │   └── aqa/
│   ├── processed/       # Extracted JSON schemas per paper (unvalidated/validated)
│   └── training/        # Final training-ready merged JSON/JSONL datasets
├── logs/                # Run execution log directory
├── tests/               # Unit and integration test suite
├── config.yaml          # Pipeline configuration values
├── requirements.txt     # Python requirements list
├── pyproject.toml       # Project packaging and development tool configs
└── README.md            # Project documentation
```

## Features

- **Double-Engine Parsing + OCR Fallback**: Utilizes **PyMuPDF** for speed and layout structure, **pdfplumber** for visual layout alignments and tables, and **PaddleOCR** as an automated fallback for scanned documents or image elements.
- **Asynchronous Scraping**: Download queues with politeness limiters, exponential backoff retries, and headers mirroring to avoid CDN/WAF blocking.
- **Data Validation**: Strict schema verification via Pydantic V2 ensuring every question conforms to strict formatting (marks, tags, sub-questions) before ingestion.

## Setup and Installation

1. Ensure you have Python 3.11+ installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. To configure the folders, scraping rules, and parser weights, create/edit `config.yaml` in the root directory.

## Pipeline Command CLI

Run pipeline actions via the CLI manager:
```bash
python main.py --help
```
Commands supported:
- `python main.py scrape --source aqa` (Scrapes links only, does not download)
- `python main.py download` (Downloads PDFs queued in link registers)
- `python main.py parse --file path/to/paper.pdf` (Runs PDF extraction and outputs structured questions)
- `python main.py process` (Processes and matches questions to mark schemes, runs validation)
