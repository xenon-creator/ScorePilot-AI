import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scorepilot.config import load_config

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("scorepilot.prepare_training_data")


def get_marks_range(marks: int) -> str:
    if marks <= 1:
        return "1"
    elif marks <= 3:
        return "2-3"
    elif marks <= 5:
        return "4-5"
    else:
        return "6+"


def stratified_split(
    records: List[Dict[str, Any]],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Splits records into train, val, and test maintaining board, subject, and marks balance."""
    groups = {}
    for r in records:
        board = r["board"]
        subject = r["subject"]
        marks = r["max_marks"]
        m_range = get_marks_range(marks)
        
        key = (board, subject, m_range)
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
        
    train_set = []
    val_set = []
    test_set = []
    
    rng = random.Random(seed)
    
    for key, group in groups.items():
        rng.shuffle(group)
        n = len(group)
        
        # Calculate split sizes with rounding and constraints for small group sizes
        if n >= 3:
            n_val = int(round(n * val_ratio))
            n_test = int(round(n * test_ratio))
            # Keep at least 1 in val/test if ratio permits
            n_val = max(1, n_val)
            n_test = max(1, n_test)
        else:
            if n == 1:
                n_val = 0
                n_test = 0
            elif n == 2:
                n_val = 1
                n_test = 0
                
        n_train = n - n_val - n_test
        # Ensure train gets at least 1 if n > 0
        if n_train <= 0 and n > 0:
            n_train = 1
            if n_val > 0:
                n_val -= 1
            elif n_test > 0:
                n_test -= 1
                
        train_set.extend(group[:n_train])
        val_set.extend(group[n_train:n_train + n_val])
        test_set.extend(group[n_train + n_val:])
        
    return train_set, val_set, test_set


def compute_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes subject, board, and marks metrics for a set of records."""
    if not records:
        return {
            "total_questions": 0,
            "average_marks": 0.0,
            "subject_counts": {},
            "board_counts": {}
        }
        
    total_marks = 0
    subjects = {}
    boards = {}
    
    for r in records:
        total_marks += r.get("max_marks", 0)
        subj = r.get("subject", "Unknown")
        board = r.get("board", "Unknown")
        
        subjects[subj] = subjects.get(subj, 0) + 1
        boards[board] = boards.get(board, 0) + 1
        
    return {
        "total_questions": len(records),
        "average_marks": round(total_marks / len(records), 2),
        "subject_counts": subjects,
        "board_counts": boards
    }


def main():
    config = load_config()
    combined_path = config.paths.processed_dir / "combined_dataset.json"
    
    if not combined_path.exists():
        logger.error(f"Combined dataset file not found at: {combined_path}")
        return
        
    logger.info(f"Loading combined dataset from {combined_path}...")
    with open(combined_path, "r", encoding="utf-8") as f:
        records = json.load(f)
        
    # Duplicate detection check
    seen_texts = set()
    duplicates_detected = 0
    for r in records:
        text = r.get("question", "")
        norm_text = "".join(text.lower().split())
        if norm_text in seen_texts:
            duplicates_detected += 1
        seen_texts.add(norm_text)
        
    logger.info(f"Duplicate detection check: {duplicates_detected} duplicates found.")
    
    # Run stratified split
    train, val, test = stratified_split(records)
    
    # Save train.jsonl, val.jsonl, test.jsonl
    training_dir = config.paths.training_dir
    training_dir.mkdir(parents=True, exist_ok=True)
    
    for name, split_data in [("train", train), ("val", val), ("test", test)]:
        out_path = training_dir / f"{name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for item in split_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(split_data)} records to: {out_path}")
        
    # Compute metrics
    overall_metrics = compute_metrics(records)
    train_metrics = compute_metrics(train)
    val_metrics = compute_metrics(val)
    test_metrics = compute_metrics(test)
    
    training_report = {
        "overall": overall_metrics,
        "splits": {
            "train": train_metrics,
            "val": val_metrics,
            "test": test_metrics
        },
        "duplicate_detection": {
            "duplicates_found": duplicates_detected,
            "status": "PASS" if duplicates_detected == 0 else "FAIL"
        }
    }
    
    # Save training_report.json
    report_path = training_dir / "training_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(training_report, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved training report to: {report_path}")
    
    print("\n" + "="*50)
    print("SCOREPILOT TRAINING DATA PREPARATION REPORT")
    print("="*50)
    print(json.dumps(training_report, indent=2))
    print("="*50 + "\n")


if __name__ == "__main__":
    main()
