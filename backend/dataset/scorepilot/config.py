import os
from pathlib import Path
from typing import Any, Dict
import yaml
from pydantic import BaseModel, Field


class ScraperSettings(BaseModel):
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User agent to use for requests"
    )
    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    concurrency_limit: int = Field(default=3, description="Max simultaneous downloads")
    rate_limit_delay: float = Field(default=2.0, description="Delay between requests in seconds")
    max_retries: int = Field(default=5, description="Maximum number of download retries")
    backoff_factor: float = Field(default=2.0, description="Exponential backoff factor")


class ParserSettings(BaseModel):
    ocr_enabled: bool = Field(default=True, description="Enable PaddleOCR fallback")
    ocr_confidence_threshold: float = Field(
        default=0.6, description="Minimum confidence for OCR matches"
    )
    dpi: int = Field(default=150, description="DPI for rendering PDF pages to images for OCR")
    extract_tables: bool = Field(default=True, description="Extract tables using pdfplumber")


class PathSettings(BaseModel):
    root_dir: Path = Field(default=Path(__file__).parent.resolve())
    raw_dir: Path = Field(default=Path(__file__).parent.resolve() / "datasets" / "raw")
    processed_dir: Path = Field(
        default=Path(__file__).parent.resolve() / "datasets" / "processed"
    )
    training_dir: Path = Field(
        default=Path(__file__).parent.resolve() / "datasets" / "training"
    )
    log_dir: Path = Field(default=Path(__file__).parent.resolve() / "logs")


class Config(BaseModel):
    scrapers: ScraperSettings = Field(default_factory=ScraperSettings)
    parsers: ParserSettings = Field(default_factory=ParserSettings)
    paths: PathSettings = Field(default_factory=PathSettings)

    def setup_directories(self) -> None:
        """Create project directories if they do not exist."""
        self.paths.raw_dir.mkdir(parents=True, exist_ok=True)
        (self.paths.raw_dir / "cbse").mkdir(parents=True, exist_ok=True)
        (self.paths.raw_dir / "aqa").mkdir(parents=True, exist_ok=True)
        self.paths.processed_dir.mkdir(parents=True, exist_ok=True)
        self.paths.training_dir.mkdir(parents=True, exist_ok=True)
        self.paths.log_dir.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Path | str | None = None) -> Config:
    """Load config from a YAML file, falling back to defaults."""
    default_config_file = Path(__file__).parent.parent / "config.yaml"
    
    if config_path is None:
        config_path = default_config_file

    config_path = Path(config_path)
    
    if not config_path.exists():
        # Return default configuration and write it as a template
        config = Config()
        config.setup_directories()
        return config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        config = Config(**data)
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path} ({e}). Using default settings.")
        config = Config()

    config.setup_directories()
    return config
