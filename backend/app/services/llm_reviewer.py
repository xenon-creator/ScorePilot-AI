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
        "You are an expert educational examiner and NLP assessment model. "
        "Your task is to grade the student's answer against the question, model answer, and marking scheme. "
        "You must return ONLY a JSON object. Do not include markdown code block formatting or backticks around the JSON. "
        "JSON format:\n"
        "{\n"
        '  "score": float,\n'
        '  "reasoning": "detailed explanation here",\n'
        '  "matched_points": ["point 1 description", "point 2"],\n'
        '  "missing_points": ["point 3 description"],\n'
        '  "confidence": float (between 0.0 and 100.0),\n'
        '  "rubric_evaluation": {\n'
        '    "coverage": float,\n'
        '    "accuracy": float,\n'
        '    "depth": float,\n'
        '    "examples": float,\n'
        '    "structure": float\n'
        "  }\n"
        "}"
    )

    user_prompt = (
        f"Question Type: {question_type}\n"
        f"Max Marks: {max_marks}\n\n"
        f"Question:\n{question}\n\n"
        f"Model Answer:\n{model_answer}\n\n"
        f"Marking Scheme:\n{scheme_str}\n\n"
        f"Student Answer:\n{student_answer}\n\n"
        "Grade the student's response. Be strict but fair. If points are partially met, you can award partial marks. "
        "For long/descriptive answers, fill the rubric_evaluation dimensions (each out of 2.0). Otherwise set rubric_evaluation to null. "
        "Ensure score does not exceed max_marks."
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

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(LLM_API_URL, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10.0) as response:
            res_body = json.loads(response.read().decode("utf-8"))
            
            # Extract assistant's reply
            choices = res_body.get("choices", [])
            if not choices:
                return None
            
            reply = choices[0].get("message", {}).get("content", "").strip()
            
            # Clean up potential markdown formatting block ```json ... ```
            if reply.startswith("```"):
                reply = re.sub(r"^```(?:json)?\n", "", reply)
                reply = re.sub(r"\n```$", "", reply)
                reply = reply.strip()
            
            res_json = json.loads(reply)
            
            # Validate and format result
            score = float(res_json.get("score", 0.0))
            score = max(0.0, min(score, max_marks))
            
            confidence = float(res_json.get("confidence", 80.0))
            confidence = max(0.0, min(confidence, 100.0))
            
            return {
                "score": score,
                "reasoning": str(res_json.get("reasoning", "")),
                "matched_points": list(res_json.get("matched_points", [])),
                "missing_points": list(res_json.get("missing_points", [])),
                "confidence": confidence,
                "rubric_evaluation": res_json.get("rubric_evaluation")
            }
            
    except Exception as e:
        logger.warning(f"LLM Reviewer failed: {e}")
        
    return None
