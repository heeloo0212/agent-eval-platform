from __future__ import annotations

import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent_client import ping_agent
from .datasets import parse_dataset_file
from .evaluator import EvaluationEngine
from .models import (
    AgentEndpoint,
    Dataset,
    EvaluationReport,
    EvaluationRequest,
    EvaluationRun,
    JudgeConfig,
    PingRequest,
    PromptTemplate,
)
from .prompts import PROMPT_TEMPLATES
from .storage import JsonStore

APP_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("AEP_DATA_DIR", APP_DIR.parent.parent / "data")).resolve()

dataset_store = JsonStore(DATA_ROOT, "datasets", Dataset)
endpoint_store = JsonStore(DATA_ROOT, "endpoints", AgentEndpoint)
judge_store = JsonStore(DATA_ROOT, "judges", JudgeConfig)
run_store = JsonStore(DATA_ROOT, "runs", EvaluationRun)
report_store = JsonStore(DATA_ROOT, "reports", EvaluationReport)
engine = EvaluationEngine(DATA_ROOT, run_store, report_store)

app = FastAPI(title="通用 Agent 评测平台", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(APP_DIR / "static" / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/datasets", response_model=Dataset)
async def upload_dataset(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
    name: str = Form(...),
    version: str = Form("v1"),
) -> Dataset:
    try:
        cases = parse_dataset_file(file.filename or "", await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    dataset = Dataset(tenant_id=tenant_id, name=name, version=version, cases=cases)
    return dataset_store.upsert(dataset)


@app.get("/api/datasets", response_model=list[Dataset])
async def list_datasets(tenant_id: str = "default") -> list[Dataset]:
    return dataset_store.list(tenant_id)


@app.get("/api/datasets/{dataset_id}", response_model=Dataset)
async def get_dataset(dataset_id: str, tenant_id: str = "default") -> Dataset:
    dataset = dataset_store.get(dataset_id, tenant_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset


@app.post("/api/endpoints", response_model=AgentEndpoint)
async def create_endpoint(endpoint: AgentEndpoint) -> AgentEndpoint:
    return endpoint_store.upsert(endpoint)


@app.get("/api/endpoints", response_model=list[AgentEndpoint])
async def list_endpoints(tenant_id: str = "default") -> list[AgentEndpoint]:
    return endpoint_store.list(tenant_id)


@app.post("/api/endpoints/{endpoint_id}/ping")
async def ping_endpoint(
    endpoint_id: str,
    request: PingRequest | None = None,
    tenant_id: str = "default",
) -> dict[str, object]:
    endpoint = endpoint_store.get(endpoint_id, tenant_id)
    if endpoint is None:
        raise HTTPException(status_code=404, detail="端点不存在")
    result = await ping_agent(endpoint, request or PingRequest())
    return result.model_dump()


@app.post("/api/judges", response_model=JudgeConfig)
async def create_judge(judge: JudgeConfig) -> JudgeConfig:
    return judge_store.upsert(judge)


@app.get("/api/judges", response_model=list[JudgeConfig])
async def list_judges(tenant_id: str = "default") -> list[JudgeConfig]:
    return judge_store.list(tenant_id)


@app.get("/api/prompts", response_model=list[PromptTemplate])
async def list_prompts() -> list[PromptTemplate]:
    return PROMPT_TEMPLATES


@app.post("/api/evaluations", response_model=EvaluationRun)
async def start_evaluation(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks,
) -> EvaluationRun:
    dataset = dataset_store.get(request.dataset_id, request.tenant_id)
    endpoint = endpoint_store.get(request.endpoint_id, request.tenant_id)
    judge = judge_store.get(request.judge_id, request.tenant_id) if request.judge_id else None

    if dataset is None:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Agent 端点不存在")
    if request.judge_id and judge is None:
        raise HTTPException(status_code=404, detail="裁判配置不存在")

    run = EvaluationRun(
        tenant_id=request.tenant_id,
        dataset_id=request.dataset_id,
        endpoint_id=request.endpoint_id,
        judge_id=request.judge_id,
        concurrency=request.concurrency,
    )
    run_store.upsert(run)
    background_tasks.add_task(engine.run, run, dataset, endpoint, judge)
    return run


@app.get("/api/evaluations", response_model=list[EvaluationRun])
async def list_evaluations(tenant_id: str = "default") -> list[EvaluationRun]:
    return run_store.list(tenant_id)


@app.get("/api/evaluations/{run_id}", response_model=EvaluationRun)
async def get_evaluation(run_id: str, tenant_id: str = "default") -> EvaluationRun:
    run = run_store.get(run_id, tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="评测任务不存在")
    return run


@app.get("/api/evaluations/{run_id}/report", response_model=EvaluationReport)
async def get_report(run_id: str, tenant_id: str = "default") -> EvaluationReport:
    report = report_store.get(run_id, tenant_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告尚未生成")
    return report
