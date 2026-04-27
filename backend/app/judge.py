from __future__ import annotations

import json
import re

import httpx

from .models import DatasetCase, JudgeConfig, JudgeProvider, JudgeScore
from .prompts import get_prompt


def _extract_json(text: str) -> dict[str, object]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _keyword_score(expected_output: str, agent_output: str) -> tuple[float, list[str]]:
    expected_terms = {
        item.strip().lower()
        for item in re.split(r"[,，;；\n、\s]+", expected_output)
        if item.strip()
    }
    if not expected_terms:
        return (5.0 if agent_output.strip() else 0.0), ["参考答案为空，使用输出非空作为弱判断"]

    output_lower = agent_output.lower()
    hits = [term for term in expected_terms if term in output_lower]
    ratio = len(hits) / len(expected_terms)
    score = round(ratio * 10, 2)
    return score, hits


def heuristic_judge(case: DatasetCase, agent_output: str, error: str | None = None) -> JudgeScore:
    if error:
        return JudgeScore(
            score=0,
            reasoning=f"Agent 请求失败或超时: {error}",
            dimensions={"accuracy": 0, "format": 0, "robustness": 0},
        )

    if not agent_output.strip():
        return JudgeScore(
            score=0,
            reasoning="Agent 输出为空。",
            dimensions={"accuracy": 0, "format": 0, "robustness": 0},
        )

    score, hits = _keyword_score(case.expected_output, agent_output)
    format_score = 10.0
    if "json" in case.query.lower() or "JSON" in case.expected_output:
        try:
            json.loads(agent_output)
        except json.JSONDecodeError:
            format_score = 4.0

    final_score = round((score * 0.7) + (format_score * 0.2) + 1.0, 2)
    final_score = min(10.0, final_score)
    return JudgeScore(
        score=final_score,
        reasoning=f"启发式裁判：命中参考要点 {hits or '无'}，格式分 {format_score}/10。",
        dimensions={
            "accuracy": round(score, 2),
            "format": format_score,
            "robustness": 10.0,
        },
    )


async def llm_judge(config: JudgeConfig, case: DatasetCase, agent_output: str) -> JudgeScore:
    if not config.base_url or not config.api_key:
        return heuristic_judge(case, agent_output)

    prompt = get_prompt(case.category).format(
        category=case.category,
        query=case.query,
        context=case.context or "",
        expected_output=case.expected_output,
        agent_output=agent_output,
    )
    payload = {
        "model": config.model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {config.api_key}"}
    url = str(config.base_url).rstrip("/") + "/chat/completions"

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        return JudgeScore.model_validate(parsed)


async def score_case(
    config: JudgeConfig | None,
    case: DatasetCase,
    agent_output: str,
    error: str | None = None,
) -> JudgeScore:
    if error or config is None or config.provider == JudgeProvider.heuristic:
        return heuristic_judge(case, agent_output, error)
    try:
        return await llm_judge(config, case, agent_output)
    except Exception as exc:
        fallback = heuristic_judge(case, agent_output)
        fallback.reasoning = f"LLM 裁判失败，已降级启发式评分。错误: {exc}. {fallback.reasoning}"
        return fallback
