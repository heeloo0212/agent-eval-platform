from backend.app.datasets import parse_dataset_file
from backend.app.evaluator import build_report
from backend.app.judge import heuristic_judge
from backend.app.models import CaseResult, DatasetCase, EvaluationRun


def test_parse_csv_dataset() -> None:
    content = (
        "Case_ID,Category,Query,Context,Expected_Output\n"
        "case_1,单轮问答,退款流程是什么,,订单号 客服 原路退回\n"
    ).encode()
    cases = parse_dataset_file("demo.csv", content)
    assert len(cases) == 1
    assert cases[0].case_id == "case_1"


def test_heuristic_judge_scores_keyword_hits() -> None:
    case = DatasetCase(
        Case_ID="case_1",
        Category="单轮问答",
        Query="退款流程是什么",
        Context=None,
        Expected_Output="订单号 客服 原路退回",
    )
    score = heuristic_judge(case, "请提供订单号，联系客服后会原路退回。")
    assert score.score >= 7


def test_build_report_aggregates_metrics() -> None:
    run = EvaluationRun(tenant_id="default", dataset_id="ds", endpoint_id="agent")
    report = build_report(
        run,
        [
            CaseResult(
                run_id=run.id,
                case_id="case_1",
                category="单轮问答",
                query="q",
                expected_output="a",
                agent_output="a",
                latency_ms=100,
                score=8,
                reasoning="ok",
            ),
            CaseResult(
                run_id=run.id,
                case_id="case_2",
                category="API 调用",
                query="q",
                expected_output="json",
                agent_output="oops",
                latency_ms=200,
                score=4,
                reasoning="bad",
            ),
        ],
    )
    assert report.average_score == 6
    assert report.pass_rate == 0.5
    assert len(report.bad_cases) == 1
