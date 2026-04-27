from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

import httpx

from .models import AgentEndpoint, AgentResult, DatasetCase, PingRequest, new_id


def _stringify_response(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("output", "answer", "response", "content", "text", "result"):
            if key in payload:
                value = payload[key]
                return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return json.dumps(payload, ensure_ascii=False)


async def _read_sse(response: httpx.Response, max_chars: int = 20000) -> str:
    chunks: list[str] = []
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            break
        chunks.append(data)
        if sum(len(chunk) for chunk in chunks) >= max_chars:
            break
    return "\n".join(chunks)


async def call_agent(endpoint: AgentEndpoint, case: DatasetCase) -> AgentResult:
    payload = {
        "Query": case.query,
        "query": case.query,
        "Context": case.context,
        "context": case.context,
        "Session_ID": new_id("session"),
        "session_id": new_id("session"),
    }
    last_error: str | None = None

    for attempt in range(endpoint.retries + 1):
        started = time.perf_counter()
        try:
            timeout = httpx.Timeout(endpoint.timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    str(endpoint.url),
                    headers=endpoint.header_dict(),
                    json=payload,
                ) as response:
                    if response.headers.get("content-type", "").startswith("text/event-stream"):
                        output = await _read_sse(response)
                    else:
                        content = await response.aread()
                        try:
                            output = _stringify_response(json.loads(content))
                        except json.JSONDecodeError:
                            output = content.decode("utf-8", errors="replace")

                    latency_ms = (time.perf_counter() - started) * 1000
                    if response.status_code >= 500:
                        last_error = f"HTTP {response.status_code}: {output[:200]}"
                        raise httpx.HTTPStatusError(last_error, request=response.request, response=response)
                    return AgentResult(
                        output=output.strip(),
                        latency_ms=round(latency_ms, 2),
                        status_code=response.status_code,
                    )
        except (httpx.TimeoutException, httpx.HTTPError, asyncio.TimeoutError) as exc:
            last_error = str(exc) or exc.__class__.__name__
            if attempt < endpoint.retries:
                await asyncio.sleep(min(2**attempt, 5))

    return AgentResult(output="", latency_ms=0, error=last_error or "请求失败")


async def ping_agent(endpoint: AgentEndpoint, request: PingRequest) -> AgentResult:
    case = DatasetCase(
        Case_ID="ping",
        Category="连接测试",
        Query=request.query,
        Context=None,
        Expected_Output="pong",
    )
    return await call_agent(endpoint, case)


async def iter_limited(tasks: list[AsyncIterator[object]]) -> AsyncIterator[object]:
    for task in tasks:
        async for item in task:
            yield item
