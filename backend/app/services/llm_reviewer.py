import os
import re
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Configurable LLM variables
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "huggingface").lower()
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("HF_TOKEN") or os.getenv("HF_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-72B-Instruct")
LLM_API_URL = os.getenv("LLM_API_URL", "https://api-inference.huggingface.co/v1/chat/completions")

def review_answer_with_llm(
    question: str,
    model_answer: str,
    marking_scheme: Dict[str, Any] | None,
    student_answer: str,
    max_marks: float,
    question_type: str
) -> Dict[str, Any] | None:
    """
    Grades a student's answer using an LLM according to the mark scheme or rubrics.
    Returns a dictionary matching the expected V2 grading format, or None if the request fails.
    """
    # Formulate schema guidelines
    scheme_str = ""
    if marking_scheme:
        if "marking_points" in marking_scheme:
            scheme_str = "Marking Points (award marks based on these specific points):\n"
            for mp in marking_scheme["marking_points"]:
                scheme_str += f"- [Point ID: {mp.get('id')}] '{mp.get('point')}' (Worth: {mp.get('marks', 1)} mark(s))\n"
        elif "rubrics" in marking_scheme:
            scheme_str = "Rubric Dimensions:\n"
            for rb in marking_scheme["rubrics"]:
                scheme_str += f"- '{rb.get('dimension')}' (Max Marks: {rb.get('max_marks')}) Description: {rb.get('description')}\n"
    else:
        # Default fallback marking scheme
        scheme_str = f"Model Answer: {model_answer}\nAssign marks based on semantic completeness and keyword match."

    system_prompt = (
        "You are ScorePilot AI, an expert educational examiner trained to evaluate student answers using mark-scheme-based assessment.\n"
        "Never grade based only on answer semantic similarity. Always prioritize concept coverage over similarity.\n"
        "Follow these steps:\n"
        "1. Identify all required key marking points from the marking scheme (or model answer if scheme is not explicitly structured).\n"
        "2. Check whether each marking point appears in the student's answer. Categorize each point as MATCHED, PARTIAL, or MISSING.\n"
        "3. Award marks based on matched concepts: MATCHED gets full credit, PARTIAL gets partial credit, MISSING gets zero credit.\n"
        "4. Generate examiner reasoning explaining what is present/missing.\n"
        "5. Generate constructive feedback outlining what should be added/corrected for full marks.\n"
        "6. Calculate grading confidence (scale 0-100) based on matched/missing counts, correctness, and lack of ambiguity.\n\n"
        "Return ONLY a valid JSON object. Do not include markdown formatting or backticks around the JSON. The JSON structure MUST be:\n"
        "{\n"
        '  "score": float,\n'
        '  "max_score": float,\n'
        '  "matched_points": ["point 1 text", ...],\n'
        '  "partial_points": ["point 2 text", ...],\n'
        '  "missing_points": ["point 3 text", ...],\n'
        '  "confidence": float,\n'
        '  "reasoning": "detailed explanation of matched/missing concepts",\n'
        '  "feedback": "constructive examiner feedback"\n'
        "}"
    )

    user_prompt = (
        f"Question:\n{question}\n\n"
        f"Maximum Marks:\n{max_marks}\n\n"
        f"Mark Scheme / Model Answer:\n{scheme_str}\n\n"
        f"Student Answer:\n{student_answer}\n\n"
        "Grade the student's answer strictly following the Examiner instructions. Ensure score does not exceed max_marks."
    )

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1000
    }

    headers = {
        "Content-Type": "application/json"
    }
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    import time
    for attempt in range(3):
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(LLM_API_URL, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10.0) as response:
                res_body = json.loads(response.read().decode("utf-8"))
                
                choices = res_body.get("choices", [])
                if not choices:
                    if "error" in res_body:
                        err_msg = res_body.get("error", "")
                        logger.warning(f"LLM API returned error on attempt {attempt + 1}: {err_msg}")
                        if "loading" in str(err_msg).lower() and attempt < 2:
                            time.sleep(3.0)
                            continue
                    return None
                
                reply = choices[0].get("message", {}).get("content", "").strip()
                if reply.startswith("```"):
                    reply = re.sub(r"^```(?:json)?\n", "", reply)
                    reply = re.sub(r"\n```$", "", reply)
                    reply = reply.strip()
                
                res_json = json.loads(reply)
                score = float(res_json.get("score", 0.0))
                score = max(0.0, min(score, max_marks))
                
                confidence = float(res_json.get("confidence", 80.0))
                confidence = max(0.0, min(confidence, 100.0))
                
                return {
                    "score": score,
                    "max_score": float(res_json.get("max_score", max_marks)),
                    "matched_points": list(res_json.get("matched_points", [])),
                    "partial_points": list(res_json.get("partial_points", [])),
                    "missing_points": list(res_json.get("missing_points", [])),
                    "confidence": confidence,
                    "reasoning": str(res_json.get("reasoning", "")),
                    "feedback": str(res_json.get("feedback", "")),
                    "rubric_evaluation": res_json.get("rubric_evaluation", None)
                }
                
        except Exception as e:
            logger.warning(f"LLM Reviewer attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(1.5)
            else:
                break
                
    return None
