from __future__ import annotations

from .models import PromptTemplate

DEFAULT_JUDGE_PROMPT = """你是一个严格、公正的 Agent 评测裁判。
请基于用户问题、参考答案、Agent 实际输出进行评分。

评分维度：
1. 事实准确性：是否覆盖 Expected_Output 的核心信息。
2. 格式合规性：是否符合 Query 中要求的输出格式。
3. 鲁棒性：是否出现报错、无意义乱码、明显拒答或空答。

请只返回 JSON：
{{
  "score": 0,
  "reasoning": "详细说明扣分原因",
  "dimensions": {{
    "accuracy": 0,
    "format": 0,
    "robustness": 0
  }}
}}

Category: {category}
Query: {query}
Context: {context}
Expected_Output: {expected_output}
Agent_Output: {agent_output}
"""


PROMPT_TEMPLATES = [
    PromptTemplate(category="单轮问答", template=DEFAULT_JUDGE_PROMPT),
    PromptTemplate(category="长文本抽取", template=DEFAULT_JUDGE_PROMPT),
    PromptTemplate(category="多步工作流", template=DEFAULT_JUDGE_PROMPT),
    PromptTemplate(category="API 调用", template=DEFAULT_JUDGE_PROMPT),
]


def get_prompt(category: str) -> str:
    for item in PROMPT_TEMPLATES:
        if item.category == category:
            return item.template
    return DEFAULT_JUDGE_PROMPT
