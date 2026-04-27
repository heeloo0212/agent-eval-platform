# 通用 Agent 评测平台

这是一个用于agent的测试的平台，包含 FastAPI 后端、浏览器可视化界面、异步评测引擎、YAML 任务落盘、报告看板和 Docker 部署配置。

## 功能

- 数据集管理：上传 CSV / JSONL，支持租户、名称和版本。
- Agent 接入：配置 HTTP POST URL、Headers、超时和重试，支持连接测试。
- 裁判配置：支持本地启发式裁判和 OpenAI 兼容裁判接口。
- 评测引擎：异步并发请求 Agent，调用裁判评分，自动生成 `config.yaml`。
- 报告看板：展示总体得分、通过率、平均延迟、分类得分和 Bad Case 详情。

## 本地启动

```bash
cd agent-eval-platform
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

打开 `http://127.0.0.1:8000`。

## Docker 启动

```bash
cd agent-eval-platform
docker compose up --build
```

## 数据集格式

CSV / JSONL 必须包含以下字段：

- `Case_ID`
- `Category`
- `Query`
- `Context`
- `Expected_Output`

可以直接上传 `examples/sample_dataset.csv` 试用。

## Agent 接口协议

平台会向被测 Agent 发送 HTTP POST：

```json
{
  "Query": "用户输入",
  "query": "用户输入",
  "Context": "上下文",
  "context": "上下文",
  "Session_ID": "session_xxx",
  "session_id": "session_xxx"
}
```

Agent 可以返回纯文本、JSON，或 SSE。JSON 中优先读取 `output`、`answer`、`response`、`content`、`text`、`result` 字段。

## 裁判接口

OpenAI 兼容裁判会调用：

```text
{base_url}/chat/completions
```

并要求返回：

```json
{
  "score": 8,
  "reasoning": "评分理由",
  "dimensions": {
    "accuracy": 8,
    "format": 9,
    "robustness": 10
  }
}
```

未配置裁判或裁判调用失败时，系统会降级到本地启发式评分，保证流程可跑通。
