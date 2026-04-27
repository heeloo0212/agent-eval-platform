from __future__ import annotations

import asyncio
from collections import defaultdict

from .agent_client import call_agent
from .config_writer import write_eval_config
from .judge import score_case
from .models import (
    AgentEndpoint,
    CaseResult,
    Dataset,
    EvaluationReport,
    EvaluationRun,
    EvaluationStatus,
    JudgeConfig,
    now_iso,
)
from .storage import JsonStore


class EvaluationEngine:
    def __init__(
        self,
        data_root,
        run_store: JsonStore[EvaluationRun],
        report_store: JsonStore[EvaluationReport],
    ) -> None:
        self.data_root = data_root
        self.run_store = run_store
        self.report_store = report_store

    async def run(
        self,
        run: EvaluationRun,
        dataset: Dataset,
        endpoint: AgentEndpoint,
        judge: JudgeConfig | None,
    ) -> None:
        run.status = EvaluationStatus.running
        run.started_at = now_iso()
        run.config_path = write_eval_config(self.data_root, run, dataset, endpoint, judge)
        self.run_store.upsert(run)

        try:
            semaphore = asyncio.Semaphore(run.concurrency)

            async def evaluate_case(case) -> CaseResult:
                async with semaphore:
                    agent_result = await call_agent(endpoint, case)
                    judge_score = await score_case(judge, case, agent_result.output, agent_result.error)
                    return CaseResult(
                        run_id=run.id,
                        case_id=case.case_id,
                        category=case.category,
                        query=case.query,
                        expected_output=case.expected_output,
                        agent_output=agent_result.output,
                        latency_ms=agent_result.latency_ms,
                        score=judge_score.score,
                        reasoning=judge_score.reasoning,
                        dimensions=judge_score.dimensions,
                        error=agent_result.error,
                    )

            results = await asyncio.gather(*(evaluate_case(case) for case in dataset.cases))
            run.status = EvaluationStatus.completed
            run.finished_at = now_iso()
            self.run_store.upsert(run)
            self.report_store.upsert(build_report(run, results))
        except Exception as exc:
            run.status = EvaluationStatus.failed
            run.error = str(exc)
            run.finished_at = now_iso()
            self.run_store.upsert(run)


def build_report(run: EvaluationRun, results: list[CaseResult]) -> EvaluationReport:
    total = len(results)
    completed = len([item for item in results if item.error is None])
    average_score = round(sum(item.score for item in results) / total, 2) if total else 0
    pass_rate = round(len([item for item in results if item.score >= 7]) / total, 4) if total else 0
    average_latency = round(sum(item.latency_ms for item in results) / total, 2) if total else 0

    category_values: dict[str, list[float]] = defaultdict(list)
    for item in results:
        category_values[item.category].append(item.score)
    category_scores = {
        category: round(sum(scores) / len(scores), 2)
        for category, scores in category_values.items()
    }
    bad_cases = sorted(
        [item for item in results if item.score < 7 or item.error],
        key=lambda item: item.score,
    )

    return EvaluationReport(
        id=run.id,
        tenant_id=run.tenant_id,
        run=run,
        total_cases=total,
        completed_cases=completed,
        average_score=average_score,
        pass_rate=pass_rate,
        average_latency_ms=average_latency,
        category_scores=category_scores,
        bad_cases=bad_cases,
        results=results,
    )
