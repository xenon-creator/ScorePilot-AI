import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field

from scorepilot.config import load_config
from scorepilot.parsers.mark_scheme_parser import MarkSchemeParser
from scorepilot.parsers.pdf_engine import ParsedDocument
from mark_scheme_structurer import MarkSchemeStructurer, MarkingPoint

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("scorepilot.generate_final_datasets")

class FinalRecord(BaseModel):
    board: str = Field(..., description="Exam board name (e.g. CBSE, AQA)")
    subject: str = Field(..., description="Subject name (e.g. Biology, Chemistry, Physics)")
    question_id: str = Field(..., description="Unique question ID")
    question: str = Field(..., description="Cleaned question text")
    max_marks: int = Field(..., description="Maximum marks for this question")
    mark_scheme: str = Field(..., description="Raw mark scheme text")
    marking_points: List[MarkingPoint] = Field(default_factory=list, description="Structured marking points")


class FinalDatasetPipeline:
    """Orchestrates final dataset generation, matching, deduplication, structuring, and validation."""

    def __init__(self):
        self.config = load_config()
        self.parser = MarkSchemeParser(self.config)
        self.structurer = MarkSchemeStructurer()
        
        # State tracking
        self.seen_texts = set()
        self.seen_ids = set()
        self.errors = []
        self.duplicates_removed = 0
        self.validation_failures = 0
        
        # Subject distribution counts
        # Key: (board, subject) -> count
        self.distribution = {}

    def is_duplicate(self, text: str, q_id: str) -> bool:
        """Determines if a question is a duplicate by text or ID."""
        norm_text = "".join(text.lower().split())
        if norm_text in self.seen_texts:
            self.duplicates_removed += 1
            return True
        if q_id in self.seen_ids:
            self.duplicates_removed += 1
            return True
        self.seen_texts.add(norm_text)
        self.seen_ids.add(q_id)
        return True

    def track_distribution(self, board: str, subject: str) -> None:
        key = (board.upper(), subject.capitalize())
        self.distribution[key] = self.distribution.get(key, 0) + 1

    def run_cbse_pipeline(self) -> List[Dict[str, Any]]:
        """Processes and structures CBSE dataset."""
        cbse_input_path = self.config.paths.processed_dir / "cbse_questions.json"
        if not cbse_input_path.exists():
            logger.error(f"CBSE matched questions file not found at: {cbse_input_path}")
            self.errors.append(f"CBSE input file missing: {cbse_input_path}")
            return []
            
        logger.info(f"Loading CBSE input data from {cbse_input_path}...")
        with open(cbse_input_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            
        processed_records = []
        for idx, item in enumerate(raw_data, 1):
            q_id = item.get("question_id", f"cbse_unknown_{idx}")
            q_text = item.get("question", "")
            max_marks = item.get("max_marks", 0)
            ms_text = item.get("mark_scheme", "")
            
            # Infer subject from ID
            subject = "Biology"
            if "chemistry" in q_id.lower():
                subject = "Chemistry"
            elif "physics" in q_id.lower():
                subject = "Physics"
                
            # Check for duplicates
            self.is_duplicate(q_text, q_id)
            
            # Extract marking points using structurer
            try:
                struct_res = self.structurer.structure(ms_text)
                marking_points = struct_res.get("marking_points", [])
            except Exception as e:
                logger.warning(f"Structurer failed for CBSE question {q_id}: {e}")
                self.errors.append(f"CBSE structurer failure for {q_id}: {e}")
                marking_points = []
                
            # Create Pydantic record
            record_dict = {
                "board": "CBSE",
                "subject": subject,
                "question_id": q_id,
                "question": q_text,
                "max_marks": max_marks,
                "mark_scheme": ms_text,
                "marking_points": marking_points
            }
            
            try:
                record = FinalRecord.model_validate(record_dict)
                processed_records.append(record.model_dump())
                self.track_distribution("CBSE", subject)
            except Exception as e:
                logger.error(f"CBSE record validation failure for {q_id}: {e}")
                self.validation_failures += 1
                self.errors.append(f"CBSE validation failure for {q_id}: {e}")
                
        logger.info(f"Processed {len(processed_records)} CBSE records.")
        return processed_records

    def run_aqa_pipeline(self) -> List[Dict[str, Any]]:
        """Processes, matches, and structures AQA dataset."""
        aqa_input_path = self.config.paths.processed_dir / "aqa_extracted_samples.json"
        if not aqa_input_path.exists():
            logger.error(f"AQA extracted questions file not found at: {aqa_input_path}")
            self.errors.append(f"AQA input file missing: {aqa_input_path}")
            return []
            
        logger.info(f"Loading AQA questions from {aqa_input_path}...")
        with open(aqa_input_path, "r", encoding="utf-8") as f:
            aqa_qs_data = json.load(f)
            
        aqa_dir = self.config.paths.raw_dir / "aqa"
        ms_files = [f for f in aqa_dir.iterdir() if f.suffix == ".pdf" and ("ms" in f.name.lower() or "mark_scheme" in f.name.lower())]
        
        # Parse all available AQA mark scheme PDFs
        parsed_ms = {}
        for ms_file in ms_files:
            try:
                doc = ParsedDocument(file_path=ms_file, pages=[])
                ms = self.parser.parse(doc, "Biology", "GCSE", 2023, "AQA")
                parsed_ms[ms_file.name] = ms
            except Exception as e:
                logger.error(f"Failed to parse AQA mark scheme {ms_file.name}: {e}")
                self.errors.append(f"AQA MS parsing failure for {ms_file.name}: {e}")
                
        processed_records = []
        
        for qp_name, qp_qs in aqa_qs_data.items():
            # Infer subject and level
            subject = "Biology"
            if "chemistry" in qp_name.lower():
                subject = "Chemistry"
            elif "physics" in qp_name.lower():
                subject = "Physics"
                
            level = "gcse" if "gcse" in qp_name.lower() else "a-level"
            
            # Find matching candidates
            candidates = []
            for ms_name, ms in parsed_ms.items():
                if subject.lower() in ms_name.lower() and level.lower() in ms_name.lower():
                    candidates.append((ms_name, ms))
                    
            if not candidates:
                logger.warning(f"No matching AQA mark scheme candidate found for question paper: {qp_name}")
                self.errors.append(f"No candidate mark scheme for {qp_name}")
                # Log all questions in this paper as unmatched
                for q in qp_qs:
                    self.errors.append(f"Unmatched question {qp_name} Q{q['question_number']}")
                continue
                
            # Select candidate with best overall question number overlap
            best_ms_name = None
            best_ms = None
            best_overlap = 0
            qp_nums = {q["question_number"] for q in qp_qs}
            
            for ms_name, ms in candidates:
                overlap = sum(1 for item in ms.items if item.question_number in qp_nums)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_ms_name = ms_name
                    best_ms = ms
                    
            if not best_ms:
                logger.warning(f"No matching mark scheme with question overlaps found for {qp_name}")
                self.errors.append(f"No overlapping mark scheme found for {qp_name}")
                continue
                
            logger.info(f"Aligned Question Paper {qp_name} with Mark Scheme {best_ms_name} ({best_overlap} overlaps)")
            
            # Map mark scheme items by question number
            ms_lookup = {item.question_number: item for item in best_ms.items}
            
            for q in qp_qs:
                q_num = q["question_number"]
                q_text = q["question_text"]
                max_marks = q["max_marks"]
                
                # Check for match
                if q_num not in ms_lookup:
                    self.errors.append(f"Unmatched question {qp_name} Q{q_num} (missing in mark scheme {best_ms_name})")
                    continue
                    
                ms_item = ms_lookup[q_num]
                ms_text = ms_item.marking_guidelines
                
                q_id = f"aqa_{subject.lower()}_{level.lower()}_{q_num.replace('.', '_')}"
                
                # Deduplicate
                self.is_duplicate(q_text, q_id)
                
                # Extract marking points using structurer
                try:
                    struct_res = self.structurer.structure(ms_text)
                    marking_points = struct_res.get("marking_points", [])
                except Exception as e:
                    logger.warning(f"Structurer failed for AQA question {q_id}: {e}")
                    self.errors.append(f"AQA structurer failure for {q_id}: {e}")
                    marking_points = []
                    
                # Create Pydantic record
                record_dict = {
                    "board": "AQA",
                    "subject": subject,
                    "question_id": q_id,
                    "question": q_text,
                    "max_marks": max_marks,
                    "mark_scheme": ms_text,
                    "marking_points": marking_points
                }
                
                try:
                    record = FinalRecord.model_validate(record_dict)
                    processed_records.append(record.model_dump())
                    self.track_distribution("AQA", subject)
                except Exception as e:
                    logger.error(f"AQA record validation failure for {q_id}: {e}")
                    self.validation_failures += 1
                    self.errors.append(f"AQA validation failure for {q_id}: {e}")
                    
        logger.info(f"Processed {len(processed_records)} AQA records.")
        return processed_records

    def generate(self) -> None:
        """Runs the entire pipeline, generates final datasets and reports."""
        logger.info("Starting Final Dataset Generation Pipeline...")
        
        # 1. Process CBSE
        cbse_records = self.run_cbse_pipeline()
        
        # 2. Process AQA
        aqa_records = self.run_aqa_pipeline()
        
        # 3. Combine
        combined_records = []
        seen_texts_combined = set()
        
        # We perform final deduplication on the combined set
        for rec in cbse_records + aqa_records:
            norm = "".join(rec["question"].lower().split())
            if norm not in seen_texts_combined:
                seen_texts_combined.add(norm)
                combined_records.append(rec)
                
        # 4. Save files
        cbse_out = self.config.paths.processed_dir / "cbse_questions.json"
        aqa_out = self.config.paths.processed_dir / "aqa_questions.json"
        combined_out = self.config.paths.processed_dir / "combined_dataset.json"
        
        with open(cbse_out, "w", encoding="utf-8") as f:
            json.dump(cbse_records, f, indent=2, ensure_ascii=False)
            
        with open(aqa_out, "w", encoding="utf-8") as f:
            json.dump(aqa_records, f, indent=2, ensure_ascii=False)
            
        with open(combined_out, "w", encoding="utf-8") as f:
            json.dump(combined_records, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Saved CBSE processed questions ({len(cbse_records)} records) to: {cbse_out}")
        logger.info(f"Saved AQA processed questions ({len(aqa_records)} records) to: {aqa_out}")
        logger.info(f"Saved combined dataset ({len(combined_records)} records) to: {combined_out}")
        
        # 5. Generate statistics and reports
        total_questions = len(cbse_records) + len(aqa_records)
        stats = {
            "total_questions_processed": total_questions,
            "cbse_questions_count": len(cbse_records),
            "aqa_questions_count": len(aqa_records),
            "combined_questions_count": len(combined_records),
            "duplicates_removed": self.duplicates_removed,
            "validation_failures": self.validation_failures
        }
        
        dist_report = []
        for (board, subj), count in self.distribution.items():
            dist_report.append({
                "board": board,
                "subject": subj,
                "count": count
            })
            
        error_report = {
            "errors_and_warnings": self.errors,
            "summary": {
                "total_failures": self.validation_failures,
                "total_errors_logged": len(self.errors)
            }
        }
        
        # Save reports
        stats_out = self.config.paths.processed_dir / "statistics.json"
        dist_out = self.config.paths.processed_dir / "subject_distribution.json"
        err_out = self.config.paths.processed_dir / "error_report.json"
        
        with open(stats_out, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        with open(dist_out, "w", encoding="utf-8") as f:
            json.dump(dist_report, f, indent=2, ensure_ascii=False)
        with open(err_out, "w", encoding="utf-8") as f:
            json.dump(error_report, f, indent=2, ensure_ascii=False)
            
        # Display reports
        print("\n" + "="*50)
        print("FINAL PIPELINE RUN STATISTICS")
        print("="*50)
        print(json.dumps(stats, indent=2))
        
        print("\n" + "="*50)
        print("SUBJECT DISTRIBUTION REPORT")
        print("="*50)
        print(json.dumps(dist_report, indent=2))
        
        print("\n" + "="*50)
        print("ERROR AND WARNING REPORT SUMMARY")
        print("="*50)
        print(f"Total Errors/Warnings Logged: {len(self.errors)}")
        print(f"Validation Failures: {self.validation_failures}")
        print("Sample errors (first 10):")
        for err in self.errors[:10]:
            print(f"- {err}")
        print("="*50 + "\n")


if __name__ == "__main__":
    pipeline = FinalDatasetPipeline()
    pipeline.generate()
