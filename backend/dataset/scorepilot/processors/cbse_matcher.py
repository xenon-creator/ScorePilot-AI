import logging
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scorepilot.config import Config

logger = logging.getLogger("scorepilot.processors.cbse_matcher")


def normalize_label(label: str) -> str:
    """Flattens a question number label to alphanumeric lowercase for robust comparison.
    
    Handles prefixes like 'Q' or 'Question' by removing them.
    Examples:
        'Q12' -> '12'
        '12(a)' -> '12a'
        '12.1' -> '121'
        '12(i)' -> '12i'
    """
    if not label:
        return ""
    # Remove leading 'q' or 'question' if followed by digits
    label_clean = re.sub(r'^(?:question|q)\s*(?=[0-9])', '', label.strip(), flags=re.IGNORECASE)
    # Remove newlines, spaces, dots, parentheses, brackets, and quotes
    s = re.sub(r'[\s\.\(\)\[\]\'\"\-]', '', label_clean).lower()
    return s


def get_digit_prefix(label: str) -> str:
    """Extracts the leading digits from a question number label."""
    # Strip leading Q/Question first
    label_clean = re.sub(r'^(?:question|q)\s*(?=[0-9])', '', label.strip(), flags=re.IGNORECASE)
    match = re.match(r'^([0-9]+)', label_clean.strip())
    return match.group(1) if match else ""


class CBSEQuestionsMatcher:
    """Production-grade matching engine to align CBSE questions with their corresponding mark schemes."""

    def __init__(self, config: Config):
        self.config = config

    def match_cbse_dataset(
        self, qp_file_path: Path, ms_file_path: Path, output_file_path: Path
    ) -> Dict[str, Any]:
        """Aligns extracted CBSE question papers and mark schemes, saves results, and calculates stats.
        
        Args:
            qp_file_path: Path to extracted questions JSON.
            ms_file_path: Path to extracted mark schemes JSON.
            output_file_path: Path to save the matched output.
            
        Returns:
            Dict containing match execution statistics per subject.
        """
        logger.info(f"Loading extracted questions from: {qp_file_path}")
        logger.info(f"Loading extracted mark schemes from: {ms_file_path}")

        with open(qp_file_path, "r", encoding="utf-8") as f:
            qp_data = json.load(f)
        with open(ms_file_path, "r", encoding="utf-8") as f:
            ms_data = json.load(f)

        all_matched_pairs: List[Dict[str, Any]] = []
        stats: Dict[str, Any] = {}

        subjects = sorted(list(set(qp_data.keys()).union(set(ms_data.keys()))))

        for subject in subjects:
            qp_list = qp_data.get(subject, [])
            ms_list = ms_data.get(subject, [])

            linked: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
            unmatched_qp = list(qp_list)
            unmatched_ms = list(ms_list)

            # Pass 1: Direct Normalized Matching
            still_unmatched_qp = []
            for qp in unmatched_qp:
                qp_norm = normalize_label(qp["question_number"])
                found_ms = None
                for ms in unmatched_ms:
                    if normalize_label(ms["question_number"]) == qp_norm:
                        found_ms = ms
                        break
                if found_ms:
                    linked.append((qp, found_ms))
                    unmatched_ms.remove(found_ms)
                else:
                    still_unmatched_qp.append(qp)
            unmatched_qp = still_unmatched_qp

            # Pass 2: Fuzzy Prefix Matching (using digit prefixes)
            still_unmatched_qp = []
            for qp in unmatched_qp:
                qp_digits = get_digit_prefix(qp["question_number"])
                if not qp_digits:
                    still_unmatched_qp.append(qp)
                    continue
                found_ms = None
                for ms in unmatched_ms:
                    if get_digit_prefix(ms["question_number"]) == qp_digits:
                        found_ms = ms
                        break
                if found_ms:
                    linked.append((qp, found_ms))
                    unmatched_ms.remove(found_ms)
                else:
                    still_unmatched_qp.append(qp)
            unmatched_qp = still_unmatched_qp

            # Build matched records for output
            subject_matched = []
            for idx, (qp, ms) in enumerate(linked, 1):
                pair_id = f"cbse_{subject.lower()}_{idx:03d}"
                # Use max marks from paper, or mark scheme if paper was 0
                max_marks = max(qp.get("max_marks", 0), ms.get("total_marks", 0))
                if max_marks == 0:
                    max_marks = qp.get("max_marks", 0) or ms.get("total_marks", 0) or 1

                subject_matched.append({
                    "question_id": pair_id,
                    "question": qp["question_text"],
                    "max_marks": max_marks,
                    "mark_scheme": ms["mark_scheme"]
                })

            all_matched_pairs.extend(subject_matched)

            total_qp_qs = len(qp_list)
            accuracy = (len(linked) / total_qp_qs * 100) if total_qp_qs > 0 else 0.0

            stats[subject] = {
                "total_linked": len(linked),
                "unmatched_paper": [q["question_number"] for q in unmatched_qp],
                "unmatched_mark_scheme": [m["question_number"] for m in unmatched_ms],
                "accuracy_estimate": accuracy
            }

        # Save merged output dataset
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(all_matched_pairs, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(all_matched_pairs)} matched pairs to {output_file_path}")
        return stats
