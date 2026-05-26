import re
import difflib
from typing import Dict, Any, List, Tuple

class ScoringService:
    @staticmethod
    def evaluate_mcq(student_answer: str, model_answer: str, max_marks: float, negative_marking: float = 0.0) -> Dict[str, Any]:
        """
        Grades Multiple Choice Questions. Supports case-insensitive matches and negative marks.
        """
        ans = student_answer.strip().upper()
        model = model_answer.strip().upper()
        
        # Take first letter or exact match
        ans_char = ans[0] if ans else ""
        model_char = model[0] if model else ""
        
        is_correct = ans_char == model_char
        
        if is_correct:
            assigned_score = max_marks
            feedback = "Correct option matching."
        else:
            # Apply negative marking if configured
            assigned_score = -abs(negative_marking) if negative_marking > 0 else 0.0
            feedback = f"Incorrect choice. Expected '{model_char}', but student wrote '{ans_char}'."
            
        return {
            "score": float(assigned_score),
            "is_correct": is_correct,
            "confidence": 1.0,
            "feedback": feedback,
            "criteria_matched": {
                "option_match": is_correct,
                "selected_option": ans_char,
                "correct_option": model_char
            }
        }

    @classmethod
    def calculate_semantic_similarity(cls, text1: str, text2: str) -> float:
        """
        Simulates transformer-based sentence embeddings similarity using a high-fidelity
        sequence matcher combined with word overlaps to mimic actual NLP models.
        """
        t1_words = set(re.findall(r'\w+', text1.lower()))
        t2_words = set(re.findall(r'\w+', text2.lower()))
        
        if not t1_words or not t2_words:
            return 0.0
            
        # Jaccard overlap
        jaccard = len(t1_words.intersection(t2_words)) / len(t1_words.union(t2_words))
        
        # Sequence matcher ratio for syntax structure
        seq_ratio = difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        
        # Blended semantic similarity score (heavy weight on conceptual overlaps)
        similarity = (jaccard * 0.7) + (seq_ratio * 0.3)
        return min(round(similarity * 1.25, 2), 1.0)  # Boost factor for conceptual matches

    @classmethod
    def evaluate_short_answer(
        cls, 
        student_answer: str, 
        model_answer: str, 
        max_marks: float, 
        keywords: List[str] = None
    ) -> Dict[str, Any]:
        """
        Grades short-form answers by blending semantic vector similarities 
        with keyword matching criteria.
        """
        if not keywords:
            keywords = []
            
        # 1. Semantic Similarity Check
        similarity = cls.calculate_semantic_similarity(student_answer, model_answer)
        
        # 2. Key Term Presence Check
        matched_keywords = []
        missing_keywords = []
        for kw in keywords:
            # Use regex for word boundaries
            if re.search(rf'\b{re.escape(kw.lower())}\b', student_answer.lower()):
                matched_keywords.append(kw)
            else:
                missing_keywords.append(kw)
                
        kw_ratio = len(matched_keywords) / len(keywords) if keywords else 1.0
        
        # Blended rating
        final_ratio = (similarity * 0.6) + (kw_ratio * 0.4)
        raw_score = final_ratio * max_marks
        
        # Cap score between 0 and max_marks
        raw_score = max(0.0, min(float(round(raw_score * 2) / 2), max_marks))  # Round to nearest 0.5
        
        # Determine confidence of score assignment. 
        # Lower confidence if writing length is short, or similarity differs wildly from keyword ratio.
        diff = abs(similarity - kw_ratio)
        confidence = max(0.4, 1.0 - (diff * 0.5))
        
        feedback = ""
        if final_ratio >= 0.85:
            feedback = "Excellent response! Captures all core concepts accurately."
        elif final_ratio >= 0.5:
            feedback = "Partially correct. Understood the primary mechanism, but missed key terms or details."
        else:
            feedback = "Incomplete response. Lacks core concepts and fails to match expected criteria."
            
        if missing_keywords:
            feedback += f" Missing concepts: {', '.join(missing_keywords[:2])}."

        return {
            "score": raw_score,
            "confidence": round(confidence, 2),
            "feedback": feedback,
            "criteria_matched": {
                "semantic_similarity_percentage": int(similarity * 100),
                "matched_keywords": matched_keywords,
                "missing_keywords": missing_keywords,
                "keyword_coverage_ratio": round(kw_ratio, 2)
            }
        }

    @classmethod
    def evaluate_long_answer(
        cls, 
        student_answer: str, 
        model_answer: str, 
        max_marks: float, 
        rubrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Grades multi-paragraph, descriptive answers using fine-grained 
        rubric parameters (e.g., structure, core claims, grammar, analysis).
        """
        # Rubrics is a list of criteria: e.g. [{"criterion": "Mechanisms", "weight": 0.4, "keywords": ["ATP", "respiration"]}]
        score_breakdown = {}
        total_assigned_ratio = 0.0
        
        matched_criteria_details = []
        suggested_feedback = []
        
        # Overall readability and size checks
        words = len(student_answer.split())
        grammar_score = 1.0
        if words < 30:
            grammar_score = 0.3
        elif words < 75:
            grammar_score = 0.7
            
        for rub in rubrics:
            crit_name = rub.get("criterion", "Concept Coverage")
            weight = rub.get("weight", 0.25)
            expected_kws = rub.get("keywords", [])
            description = rub.get("description", "")
            
            # Evaluate this rubric criterion
            crit_matches = []
            crit_missing = []
            for kw in expected_kws:
                if re.search(rf'\b{re.escape(kw.lower())}\b', student_answer.lower()):
                    crit_matches.append(kw)
                else:
                    crit_missing.append(kw)
            
            # Sub-score calculations
            match_ratio = len(crit_matches) / len(expected_kws) if expected_kws else 1.0
            semantic_overlap = cls.calculate_semantic_similarity(student_answer, model_answer)
            
            # Blended weight for this specific rubric block
            crit_ratio = (match_ratio * 0.7) + (semantic_overlap * 0.3)
            if crit_name.lower() == "grammar" or "structure" in crit_name.lower():
                crit_ratio = (crit_ratio * 0.4) + (grammar_score * 0.6)
                
            crit_ratio = min(1.0, max(0.0, crit_ratio))
            criterion_score = crit_ratio * (max_marks * weight)
            
            total_assigned_ratio += crit_ratio * weight
            score_breakdown[crit_name] = round(criterion_score, 2)
            
            # Document details
            matched_criteria_details.append({
                "criterion": crit_name,
                "description": description,
                "weight": weight,
                "matched_points": crit_matches,
                "missing_points": crit_missing,
                "coverage_percentage": int(crit_ratio * 100),
                "score_allocated": round(criterion_score, 2),
                "max_score_allocated": round(max_marks * weight, 2)
            })
            
            if crit_ratio < 0.6:
                suggested_feedback.append(f"Enhance depth in '{crit_name}'. Missing concept: {', '.join(crit_missing[:2]) or 'lacks structure'}.")
            else:
                suggested_feedback.append(f"Strong understanding demonstrated in '{crit_name}'.")

        final_score = total_assigned_ratio * max_marks
        final_score = max(0.0, min(float(round(final_score * 2) / 2), max_marks))  # Round to nearest 0.5
        
        # Calculate overall system confidence in grading
        # Short responses to long essays trigger low AI confidence (requires teacher verification)
        base_confidence = 0.90
        if words < 50:
            base_confidence -= 0.30
        if any(item["coverage_percentage"] < 40 for item in matched_criteria_details):
            base_confidence -= 0.10
            
        confidence = max(0.5, round(base_confidence, 2))
        
        return {
            "score": final_score,
            "confidence": confidence,
            "feedback": " | ".join(suggested_feedback[:3]),
            "criteria_matched": {
                "score_breakdown": score_breakdown,
                "criteria_details": matched_criteria_details,
                "word_count": words,
                "readability_score": int(grammar_score * 100)
            }
        }
