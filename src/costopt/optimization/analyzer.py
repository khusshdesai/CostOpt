"""
Request Analysis Layer for CostOpt Intelligent Optimization Engine
"""

import re
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class AnalysisResult:
    task_type: str  # 'simple_classification', 'extraction', 'summarization', 'reasoning', 'coding', 'creative_generation', 'general_chat'
    complexity: str  # 'low', 'medium', 'high'
    confidence: float  # 0.0 to 1.0
    estimated_prompt_tokens: int
    signals: List[str]

class RequestAnalyzer:
    def __init__(self):
        self._patterns = {
            "simple_classification": [
                r"\b(classify|sentiment|yes/no|label|category|rating|is this|spam|true/false)\b"
            ],
            "extraction": [
                r"\b(extract|parse|convert to json|find entities|json|csv|table|regex|pull out)\b"
            ],
            "summarization": [
                r"\b(summarize|summary|tldr|brief|key takeaways|digest|overview|bullet points)\b"
            ],
            "coding": [
                r"```|def |function |class |import |public static|void |syntax|refactor|debug|python|javascript|rust|go\b"
            ],
            "reasoning": [
                r"\b(step[ -]by[ -]step|prove|proof|math|equation|logic|derive|why did|root cause|calculate|analyze)\b"
            ],
            "creative_generation": [
                r"\b(story|poem|essay|song|imagine|draft an email|script|fictional)\b"
            ]
        }

    def analyze(self, prompt: str, requested_model: str) -> AnalysisResult:
        prompt_len = len(prompt)
        prompt_lower = prompt.lower()
        est_tokens = max(1, prompt_len // 4)
        signals = []

        # 1. Determine Task Type
        task_type = "general_chat"
        highest_match_count = 0

        for t_type, patterns in self._patterns.items():
            match_count = 0
            for pattern in patterns:
                matches = re.findall(pattern, prompt_lower, re.IGNORECASE)
                if matches:
                    match_count += len(matches)
            
            if match_count > highest_match_count:
                highest_match_count = match_count
                task_type = t_type

        if highest_match_count > 0:
            signals.append(f"Matched task signals for {task_type} (frequency: {highest_match_count})")
        else:
            signals.append("No explicit task signals matched; defaulted to general_chat")

        # 2. Determine Complexity
        complexity = "medium"
        
        # High complexity signals
        has_code_blocks = "```" in prompt
        has_multistep = any(w in prompt_lower for w in ["step by step", "first,", "second,", "finally,"])
        
        if prompt_len > 1500 or (has_code_blocks and task_type == "coding") or (has_multistep and task_type == "reasoning"):
            complexity = "high"
            signals.append("High complexity flag: long prompt or multi-step reasoning/code logic")
        elif prompt_len < 300 and task_type in ["simple_classification", "extraction"]:
            complexity = "low"
            signals.append("Low complexity flag: short prompt length and structured task")
        else:
            complexity = "medium"
            signals.append("Medium complexity: standard request density")

        # 3. Calculate Confidence Score
        confidence = 0.80
        if task_type == "simple_classification" and complexity == "low":
            confidence = 0.95
        elif task_type in ["extraction", "summarization"] and complexity == "low":
            confidence = 0.90
        elif task_type in ["coding", "reasoning"] and complexity == "high":
            confidence = 0.88
        elif task_type == "general_chat":
            confidence = 0.72

        return AnalysisResult(
            task_type=task_type,
            complexity=complexity,
            confidence=confidence,
            estimated_prompt_tokens=est_tokens,
            signals=signals
        )
