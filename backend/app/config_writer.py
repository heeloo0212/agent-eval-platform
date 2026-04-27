from __future__ import annotations

from pathlib import Path

import yaml

from .models import AgentEndpoint, Dataset, EvaluationRun, JudgeConfig


def write_eval_config(
    root: Path,
    run: EvaluationRun,
    dataset: Dataset,
    endpoint: AgentEndpoint,
    judge: JudgeConfig | None,
) -> str:
    config_dir = root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / f"{run.id}.yaml"
    payload = {
        "run_id": run.id,
        "tenant_id": run.tenant_id,
        "dataset": {
            "id": dataset.id,
            "name": dataset.name,
            "version": dataset.version,
            "case_count": len(dataset.cases),
        },
        "agent_endpoint": {
            "id": endpoint.id,
            "name": endpoint.name,
            "url": str(endpoint.url),
            "headers": [item.model_dump() for item in endpoint.headers],
            "timeout_seconds": endpoint.timeout_seconds,
            "retries": endpoint.retries,
        },
        "judge": None
        if judge is None
        else {
            "id": judge.id,
            "name": judge.name,
            "provider": judge.provider.value,
            "model_name": judge.model_name,
            "base_url": str(judge.base_url) if judge.base_url else None,
            "temperature": judge.temperature,
        },
        "concurrency": run.concurrency,
    }
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(path)
