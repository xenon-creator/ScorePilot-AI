import json
import os
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Define Pydantic Models for JSON Validation
class MarkingPoint(BaseModel):
    point: str = Field(..., description="The concept, keyword or answer detail required to get the marks.")
    marks: int = Field(..., description="Number of marks allocated to this point.")

class StructuredMarkScheme(BaseModel):
    marking_points: List[MarkingPoint] = Field(..., description="List of marking points.")


class MarkSchemeStructurer:
    """Structuring engine for exam marking schemes, prioritizing rules with LLM fallback."""

    def __init__(self):
        # Compiled patterns for rule-based extraction
        self.word_to_num = {
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
            "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
            "a": "1", "an": "1"
        }
        
        # Regex patterns to extract point and marks from normalized segments
        self.patterns = [
            # 1. Award X marks for POINT
            # 1. Award X marks for POINT
            (re.compile(r'^(?:award|give|allow)\s+(\d+)\s+marks?\s+for\s+(.*)$', re.IGNORECASE), True),
            # 2. X marks for POINT
            (re.compile(r'^(\d+)\s+marks?\s+for\s+(.*)$', re.IGNORECASE), True),
            # 3. X marks: POINT
            (re.compile(r'^(\d+)\s+marks?\s*:\s*(.*)$', re.IGNORECASE), True),
            # 4. POINT [X marks] or POINT (X marks)
            (re.compile(r'^(.*?)\s*[\(\[-]\s*(\d+)\s*marks?\s*[\)\]]?$', re.IGNORECASE), False),
            # 5. POINT (X)
            (re.compile(r'^(.*?)\s+\(\s*(\d+)\s*\)$', re.IGNORECASE), False),
            # 6. POINT - X marks
            (re.compile(r'^(.*?)\s*-\s*(\d+)\s*marks?$', re.IGNORECASE), False),
            # 7. Award POINT X marks
            (re.compile(r'^(?:award|give)\s+(.*?)\s+(\d+)\s+marks?$', re.IGNORECASE), False),
            # 8. Accept/allow POINT [X marks]
            (re.compile(r'^(?:accept|allow)\s+(.*?)\s+\[\s*(\d+)\s*marks?\s*\]$', re.IGNORECASE), False),
            # 9. POINT for X marks
            (re.compile(r'^(.*?)\s+for\s+(\d+)\s+marks?$', re.IGNORECASE), False)
        ]

    def text_to_digit(self, text: str) -> str:
        """Converts number words to digits when associated with marks."""
        for word, num in self.word_to_num.items():
            text = re.sub(r'\b' + word + r'\s+(?=marks?\b)', num + ' ', text, flags=re.IGNORECASE)
        return text

    def split_segments(self, text: str) -> List[str]:
        """Splits raw text into clean, single-point candidate segments."""
        # Standardize separators
        text = text.replace('\n', '. ').replace(';', '. ')
        
        # Split by periods not followed by a digit
        parts = re.split(r'\.(?!\d)\s*', text)
        
        final_segments = []
        mark_indicators = [r'\b\d+\s+marks?\b', r'\bmarks?\s+\d+\b', r'\b\d+\s*marks?\b', r'\b\(\d+\)\b']
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            # Split by "and" if both sides have mark indicators
            if " and " in part.lower():
                subparts = re.split(r'\s+and\s+', part, flags=re.IGNORECASE)
                has_marks = [any(re.search(pat, sp, re.IGNORECASE) for pat in mark_indicators) for sp in subparts]
                if len(subparts) > 1 and all(has_marks):
                    final_segments.extend(subparts)
                else:
                    final_segments.append(part)
            else:
                final_segments.append(part)
                
        return [s.strip() for s in final_segments if s.strip()]

    def clean_point(self, point: str) -> str:
        """Strips leading verbs, helper words, and surrounding punctuation from a point."""
        point = point.strip()
        # Remove surrounding quotes or brackets
        point = re.sub(r'^[\'\"\(\[\{\s]+|[\'\"\)\}\]\s]+$', '', point)
        
        prefixes = [
            r'^mentioning\s+both\s+',
            r'^mentioning\s+',
            r'^mention\s+of\s+',
            r'^mention\s+',
            r'^stating\s+',
            r'^state\s+',
            r'^suggesting\s+',
            r'^suggest\s+',
            r'^identifying\s+',
            r'^identify\s+',
            r'^explaining\s+',
            r'^explain\s+',
            r'^showing\s+',
            r'^show\s+',
            r'^writing\s+',
            r'^write\s+',
            r'^giving\s+',
            r'^give\s+',
            r'^describing\s+',
            r'^describe\s+',
            r'^correct\s+',
            r'^reference\s+to\s+',
            r'^referring\s+to\s+',
            r'^any\s+one\s+from\s+',
            r'^any\s+two\s+from\s+',
            r'^accept\s+',
            r'^allow\s+',
            r'^for\s+'
        ]
        
        changed = True
        while changed:
            changed = False
            for pref in prefixes:
                new_point = re.sub(pref, '', point, flags=re.IGNORECASE)
                if new_point != point:
                    point = new_point
                    changed = True
                    break
                    
        point = re.sub(r'[.,;:\s]+$', '', point)
        point = re.sub(r'^[.,;:\s]+', '', point)
        return point.strip()

    def rule_based_extract(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """Tries to extract structured points using rule-based parsing."""
        segments = self.split_segments(text)
        points_list = []
        
        for seg in segments:
            # Skip reject/negative guidelines
            if any(neg in seg.lower() for neg in ["reject", "do not accept", "ignore"]):
                continue
                
            normalized = self.text_to_digit(seg)
            # Remove leading bullet symbols, numbers, hyphens
            normalized = re.sub(r'^(?:[-\*\•\s]|\d+\.\s*|\d+\)\s*|\(\d+\)\s*)+', '', normalized).strip()
            
            matched = False
            for pattern, marks_first in self.patterns:
                match = pattern.match(normalized)
                if match:
                    if marks_first:
                        marks_str, point_str = match.group(1), match.group(2)
                    else:
                        point_str, marks_str = match.group(1), match.group(2)
                        
                    try:
                        marks = int(marks_str)
                    except ValueError:
                        continue
                        
                    cleaned_pt = self.clean_point(point_str)
                    if cleaned_pt:
                        points_list.append({"point": cleaned_pt, "marks": marks})
                        matched = True
                        break
            
            # If a segment has mark keywords but failed rule matching, we must fallback to LLM
            if not matched and any(indicator in seg.lower() for indicator in ["mark", "marks", "(1", "(2", "(3"]):
                return None
                
        return points_list if points_list else None

    def llm_fallback(self, text: str) -> Dict[str, Any]:
        """Uses an LLM to structure complex syntactic marking points."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("LLM fallback triggered but OPENAI_API_KEY is not configured in the environment.")
            
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            prompt = (
                "You are an expert exam mark scheme parser.\n"
                "Structure the following raw mark scheme text into marking points and their allocated marks.\n"
                "Return ONLY a valid JSON object matching this schema:\n"
                "{\n"
                "  \"marking_points\": [\n"
                "    {\"point\": \"string\", \"marks\": integer}\n"
                "  ]\n"
                "}\n\n"
                f"Text:\n\"{text}\""
            )
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            raise RuntimeError(f"LLM fallback failed: {e}")

    def structure(self, text: str) -> Dict[str, Any]:
        """Main entry point. Runs rule extraction first, falling back to LLM if needed."""
        # 1. Run rule-based extraction
        rule_results = self.rule_based_extract(text)
        
        if rule_results is not None:
            output = {"marking_points": rule_results}
        else:
            # 2. Fall back to LLM
            output = self.llm_fallback(text)
            
        # 3. Validate JSON via Pydantic schema
        validated = StructuredMarkScheme.model_validate(output)
        return validated.model_dump()


def run_evaluation() -> None:
    """Generates 100 test examples, runs the structuring engine, and reports success rate."""
    structurer = MarkSchemeStructurer()
    
    # 10 templates x 10 points = 100 examples
    templates = [
        ("Award one mark for mentioning {point}.", [{"point": "{point}", "marks": 1}]),
        ("Award {marks} marks for stating {point}.", [{"point": "{point}", "marks": "{marks}"}]),
        ("One mark for {point}.", [{"point": "{point}", "marks": 1}]),
        ("Give {marks} marks for {point}.", [{"point": "{point}", "marks": "{marks}"}]),
        ("{point} (1 mark)", [{"point": "{point}", "marks": 1}]),
        ("{point} [{marks} marks]", [{"point": "{point}", "marks": "{marks}"}]),
        ("State {point} for 1 mark.", [{"point": "{point}", "marks": 1}]),
        ("{point} ({marks})", [{"point": "{point}", "marks": "{marks}"}]),
        ("Award 1 mark for {point} and 1 mark for {point2}.", [{"point": "{point}", "marks": 1}, {"point": "{point2}", "marks": 1}]),
        ("{point} - {marks} marks", [{"point": "{point}", "marks": "{marks}"}])
    ]
    
    points = [
        "sunlight", "carbon dioxide", "water", "oxygen", "chlorophyll",
        "glucose", "temperature", "pH level", "active site", "denaturation"
    ]
    
    test_cases = []
    
    for idx in range(100):
        template, expected = templates[idx % len(templates)]
        pt = points[idx % len(points)]
        pt2 = points[(idx + 1) % len(points)]
        marks = (idx % 3) + 1
        
        input_text = template.format(point=pt, point2=pt2, marks=marks)
        
        # Build exact expected results
        expected_points = []
        for exp in expected:
            m = exp["marks"]
            if m == "{marks}":
                m = marks
            p = exp["point"].format(point=pt, point2=pt2)
            expected_points.append({"point": p, "marks": int(m)})
            
        test_cases.append({
            "input": input_text,
            "expected": expected_points
        })

    print("==================================================")
    print("Evaluating Mark Scheme Structuring Engine (100 Cases)")
    print("==================================================")
    
    passed_count = 0
    
    for idx, case in enumerate(test_cases, 1):
        input_str = case["input"]
        expected_pts = case["expected"]
        
        try:
            result = structurer.structure(input_str)
            actual_pts = result["marking_points"]
            
            # Compare point by point
            if len(actual_pts) == len(expected_pts):
                match = True
                for act, exp in zip(actual_pts, expected_pts):
                    if act["point"].lower() != exp["point"].lower() or act["marks"] != exp["marks"]:
                        match = False
                        break
                if match:
                    passed_count += 1
                else:
                    print(f"Mismatch Case {idx}:")
                    print(f"  Input   : {input_str}")
                    print(f"  Expected: {expected_pts}")
                    print(f"  Actual  : {actual_pts}\n")
            else:
                print(f"Mismatch Count Case {idx}:")
                print(f"  Input   : {input_str}")
                print(f"  Expected: {expected_pts}")
                print(f"  Actual  : {actual_pts}\n")
                
        except Exception as e:
            print(f"Error Case {idx}: {e}")
            
    success_rate = (passed_count / 100) * 100
    print(f"\nEvaluation Results:")
    print(f"- Total Test Cases : 100")
    print(f"- Passed Cases     : {passed_count}")
    print(f"- Failed Cases     : {100 - passed_count}")
    print(f"- Success Rate     : {success_rate:.1f}%")


if __name__ == "__main__":
    run_evaluation()
