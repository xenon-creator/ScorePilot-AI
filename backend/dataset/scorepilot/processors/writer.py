import json
import logging
from pathlib import Path
from typing import Any, Dict, List
from scorepilot.config import Config
from scorepilot.validators.schemas import MergedDataset

logger = logging.getLogger("scorepilot.processors.writer")


class DatasetWriter:
    """Handles persistence of parsed papers and compilation of final AI training files."""

    def __init__(self, config: Config):
        self.config = config

    def save_processed_paper(self, dataset: MergedDataset) -> Path:
        """Saves a single merged exam-mark scheme paper dataset to the processed folder."""
        self.config.setup_directories()
        out_path = self.config.paths.processed_dir / f"{dataset.paper_id}.json"
        
        try:
            # Pydantic dump_model returns a serializable dict
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(dataset.model_dump(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved processed dataset to: {out_path}")
            return out_path
        except Exception as e:
            logger.error(f"Failed to save processed dataset to {out_path}: {e}")
            raise

    def compile_training_dataset(
        self,
        paper_ids: List[str],
        output_filename: str,
        export_format: str = "jsonl",
        prompt_template: str = "Question:\n{question}\n\nMarks: {marks}\n"
    ) -> Path:
        """Compiles multiple processed papers into a single training-ready file.
        
        Formats supported:
            - 'json': A list of all merged pairs.
            - 'jsonl': Instruction-response format (one JSON object per line)
                      specifically formatted for LLM fine-tuning.
        """
        self.config.setup_directories()
        
        # Determine output file path
        if not output_filename.endswith(f".{export_format}"):
            output_filename += f".{export_format}"
        out_path = self.config.paths.training_dir / output_filename
        
        compiled_pairs: List[Dict[str, Any]] = []
        
        # Load and collect pairs from specified processed paper files
        for paper_id in paper_ids:
            file_path = self.config.paths.processed_dir / f"{paper_id}.json"
            if not file_path.exists():
                logger.warning(f"Processed file {file_path.name} not found. Skipping compilation.")
                continue
                
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # Load via Pydantic model for security check
                paper_dataset = MergedDataset(**data)
                
                for pair in paper_dataset.pairs:
                    # Format standard instruction-tuning structure
                    user_prompt = prompt_template.format(
                        question=pair.question_text,
                        marks=pair.marks or "Not Specified"
                    )
                    
                    compiled_pairs.append({
                        "id": pair.question_id,
                        "paper_id": paper_dataset.paper_id,
                        "board": paper_dataset.board,
                        "subject": paper_dataset.subject,
                        "level": paper_dataset.level,
                        "year": paper_dataset.year,
                        "instruction": "Provide the marking guidelines and solutions for the following exam question.",
                        "input": user_prompt,
                        "output": pair.marking_guidelines,
                        "answer_key": pair.answer_key,
                        "images": pair.images,
                        "metadata": pair.metadata
                    })
            except Exception as e:
                logger.error(f"Failed to read processed paper {paper_id}: {e}")
                continue

        logger.info(f"Compiling {len(compiled_pairs)} pairs to {out_path}...")
        
        try:
            if export_format == "json":
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(compiled_pairs, f, indent=2, ensure_ascii=False)
            elif export_format == "jsonl":
                with open(out_path, "w", encoding="utf-8") as f:
                    for pair in compiled_pairs:
                        f.write(json.dumps(pair, ensure_ascii=False) + "\n")
            else:
                raise ValueError(f"Unsupported export format: {export_format}")
                
            logger.info(f"Successfully compiled training set containing {len(compiled_pairs)} items.")
            return out_path
        except Exception as e:
            logger.error(f"Failed to write training dataset to {out_path}: {e}")
            raise
