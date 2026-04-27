const state = {
  datasets: [],
  endpoints: [],
  judges: [],
  runs: [],
  report: null,
};

const $ = (selector) => document.querySelector(selector);

function toast(message) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showView(viewId) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-link").forEach((link) => link.classList.remove("active"));
  $(`#${viewId}`).classList.add("active");
  const nav = document.querySelector(`[data-view="${viewId}"]`);
  if (nav) nav.classList.add("active");
}

function optionList(select, items, placeholder) {
  select.innerHTML = `<option value="">${placeholder}</option>`;
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = `${item.name} (${item.id})`;
    select.appendChild(option);
  }
}

function statusTone(value, reverse = false) {
  const number = Number(value);
  if (reverse) {
    if (number <= 1) return "good";
    if (number <= 5) return "warn";
    return "bad";
  }
  if (number >= 80 || number >= 8) return "good";
  if (number >= 60 || number >= 6) return "warn";
  return "bad";
}

function renderLists() {
  $("#datasets").innerHTML = state.datasets
    .map(
      (item) => `
        <div class="item">
          <strong>${escapeHtml(item.name)} ${escapeHtml(item.version)}</strong>
          <small>${item.id} · ${item.cases.length} cases · ${item.tenant_id}</small>
        </div>
      `,
    )
    .join("");

  $("#endpoints").innerHTML = state.endpoints
    .map(
      (item) => `
        <div class="item">
          <strong>${escapeHtml(item.name)}</strong>
          <small>${escapeHtml(item.url)} · timeout ${item.timeout_seconds}s · retry ${item.retries}</small>
          <button class="secondary" onclick="pingEndpoint('${item.id}')">测试连接</button>
        </div>
      `,
    )
    .join("");

  $("#judges").innerHTML = state.judges
    .map(
      (item) => `
        <div class="item">
          <strong>${escapeHtml(item.name)}</strong>
          <small>${item.provider} · ${escapeHtml(item.model_name)}</small>
        </div>
      `,
    )
    .join("");

  optionList($("[name=dataset_id]"), state.datasets, "选择数据集");
  optionList($("[name=endpoint_id]"), state.endpoints, "选择 Agent 端点");
  optionList($("[name=judge_id]"), state.judges, "不选择则使用启发式裁判");

  $("#runPicker").innerHTML = `<option value="">选择评测任务</option>${state.runs
    .map((run) => `<option value="${run.id}">${run.id} · ${run.status}</option>`)
    .join("")}`;
  updateConfigPreview();
}

async function refresh() {
  const tenantId = document.querySelector("#evaluationForm [name=tenant_id]").value || "default";
  const [datasets, endpoints, judges, runs] = await Promise.all([
    api(`/api/datasets?tenant_id=${encodeURIComponent(tenantId)}`),
    api(`/api/endpoints?tenant_id=${encodeURIComponent(tenantId)}`),
    api(`/api/judges?tenant_id=${encodeURIComponent(tenantId)}`),
    api(`/api/evaluations?tenant_id=${encodeURIComponent(tenantId)}`),
  ]);
  state.datasets = datasets;
  state.endpoints = endpoints;
  state.judges = judges;
  state.runs = runs;
  renderLists();

  const completed = runs.find((run) => run.status === "completed");
  if (completed) {
    $("#runPicker").value = completed.id;
    await loadReport(completed.id, false);
  } else {
    renderEmptyDashboard();
  }
}

function renderEmptyDashboard() {
  $("#dashboardTaskName").textContent = "暂无评测任务";
  $("#overview").innerHTML = [
    ["得分", "- / 10", "warn"],
    ["成功率", "-", "warn"],
    ["平均延迟", "-", "warn"],
    ["异常率", "-", "warn"],
  ]
    .map(([label, value, tone]) => `<div class="metric"><span>${label}</span><strong>${value}</strong><small class="${tone}">●</small></div>`)
    .join("");
  $("#badCaseRows").innerHTML = `<tr><td colspan="4">暂无报告，请先启动一次评测。</td></tr>`;
  drawRadar({});
}

async function pingEndpoint(id) {
  try {
    const result = await api(`/api/endpoints/${id}/ping`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "ping" }),
    });
    toast(result.error ? `连接失败: ${result.error}` : `连接成功: ${result.output || result.status_code}`);
  } catch (error) {
    toast(error.message);
  }
}

async function loadReport(runId, jump = true) {
  try {
    const report = await api(`/api/evaluations/${runId}/report`);
    state.report = report;
    $("#runPicker").value = runId;
    renderReport(report);
    if (jump) showView("dashboardView");
  } catch (error) {
    toast(error.message);
  }
}

function renderReport(report) {
  const exceptionRate = report.total_cases
    ? ((report.total_cases - report.completed_cases) / report.total_cases) * 100
    : 0;
  const successRate = Math.round(report.pass_rate * 1000) / 10;
  const latencySeconds = Math.round((report.average_latency_ms / 1000) * 10) / 10;

  $("#dashboardTaskName").textContent = `${report.run.id} (${report.run.status})`;
  $("#overview").innerHTML = [
    ["得分", `${report.average_score} / 10`, statusTone(report.average_score)],
    ["成功率", `${successRate}%`, statusTone(successRate)],
    ["平均延迟", `${latencySeconds}s`, latencySeconds <= 1 ? "good" : latencySeconds <= 3 ? "warn" : "bad"],
    ["异常率", `${exceptionRate.toFixed(1)}%`, statusTone(exceptionRate, true)],
  ]
    .map(([label, value, tone]) => `<div class="metric"><span>${label}</span><strong>${value}</strong><small class="${tone}">●</small></div>`)
    .join("");

  drawRadar(report.category_scores);
  $("#badCaseRows").innerHTML = report.bad_cases.length
    ? report.bad_cases
        .slice(0, 12)
        .map(
          (item) => `
            <tr class="clickable" onclick="showCaseDetail('${item.case_id}')">
              <td>${escapeHtml(item.case_id)}</td>
              <td>${escapeHtml(item.category)}</td>
              <td>10</td>
              <td><strong class="${statusTone(item.score)}">${item.score}</strong></td>
            </tr>
          `,
        )
        .join("")
    : `<tr><td colspan="4">没有失败用例。</td></tr>`;
}

function drawRadar(scores) {
  const canvas = $("#radar");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const entries = Object.entries(scores);
  if (!entries.length) {
    ctx.fillStyle = "#6c7a92";
    ctx.font = "16px sans-serif";
    ctx.fillText("暂无分类得分", 24, 42);
    return;
  }

  const cx = canvas.width / 2;
  const cy = canvas.height / 2 + 12;
  const radius = Math.min(canvas.width, canvas.height) * 0.34;
  const axes = entries.slice(0, 6);

  ctx.strokeStyle = "#dfe6f2";
  ctx.fillStyle = "#f6f8ff";
  for (let level = 1; level <= 5; level += 1) {
    ctx.beginPath();
    axes.forEach((_, index) => {
      const angle = (Math.PI * 2 * index) / axes.length - Math.PI / 2;
      const r = (radius * level) / 5;
      const x = cx + Math.cos(angle) * r;
      const y = cy + Math.sin(angle) * r;
      index === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.closePath();
    ctx.stroke();
  }

  ctx.beginPath();
  axes.forEach(([label, score], index) => {
    const angle = (Math.PI * 2 * index) / axes.length - Math.PI / 2;
    const axisX = cx + Math.cos(angle) * radius;
    const axisY = cy + Math.sin(angle) * radius;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(axisX, axisY);
    ctx.stroke();
    ctx.fillStyle = "#526078";
    ctx.fillText(label, cx + Math.cos(angle) * (radius + 28) - 24, cy + Math.sin(angle) * (radius + 28));
  });

  ctx.beginPath();
  axes.forEach(([, score], index) => {
    const angle = (Math.PI * 2 * index) / axes.length - Math.PI / 2;
    const r = radius * (Number(score) / 10);
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    index === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = "rgb(49 94 251 / 22%)";
  ctx.strokeStyle = "#315efb";
  ctx.lineWidth = 3;
  ctx.fill();
  ctx.stroke();
  ctx.lineWidth = 1;
}

function showCaseDetail(caseId) {
  const item = state.report?.results.find((result) => result.case_id === caseId);
  if (!item) return;
  $("#caseTitle").textContent = `🔍 用例详情 (Case ID: ${item.case_id}) - 评测状态: ${item.score >= 7 ? "✅ 通过" : "❌ 失败"} (得分: ${item.score}/10)`;
  $("#caseQuery").textContent = item.query;
  $("#caseExpected").textContent = item.expected_output;
  $("#caseActual").textContent = item.agent_output || item.error || "";
  $("#caseReasoning").textContent = JSON.stringify(
    {
      score: item.score,
      reasoning: item.reasoning,
      dimensions: item.dimensions,
      error: item.error,
    },
    null,
    2,
  );
  showView("caseView");
}

function updateConfigPreview() {
  const form = $("#evaluationForm");
  const dataset = state.datasets.find((item) => item.id === form.dataset_id.value);
  const endpoint = state.endpoints.find((item) => item.id === form.endpoint_id.value);
  const judge = state.judges.find((item) => item.id === form.judge_id.value);
  const concurrency = form.concurrency.value || 5;

  $("#selectedEndpoint").textContent = endpoint
    ? `${endpoint.name} · ${endpoint.url} · timeout ${endpoint.timeout_seconds}s · retry ${endpoint.retries}`
    : "请选择目标端点";
  $("#selectedJudge").textContent = judge ? `${judge.name} · ${judge.model_name} · ${judge.provider}` : "未选择时使用启发式裁判";

  $("#yamlPreview").value = [
    `name: "${dataset?.name || "New_Agent_Eval_Task"}"`,
    `tenant_id: "${form.tenant_id.value || "default"}"`,
    `dataset_id: "${dataset?.id || "select_dataset"}"`,
    "target:",
    `  endpoint: "${endpoint?.url || "http://localhost:8000/v1"}"`,
    `  timeout: ${endpoint?.timeout_seconds || 60}`,
    `  retry: ${endpoint?.retries || 1}`,
    "judge:",
    `  model: "${judge?.model_name || "heuristic-v1"}"`,
    `  provider: "${judge?.provider || "heuristic"}"`,
    `  mode: "strict_json"`,
    "runner:",
    `  strategy: "asyncio"`,
    `  concurrency: ${concurrency}`,
  ].join("\n");
}

$("#datasetForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/datasets", { method: "POST", body: new FormData(event.target) });
    toast("数据集已上传");
    event.target.reset();
    await refresh();
  } catch (error) {
    toast(error.message);
  }
});

$("#endpointForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    const headersText = form.get("headers") || "[]";
    const payload = {
      tenant_id: form.get("tenant_id"),
      name: form.get("name"),
      url: form.get("url"),
      headers: JSON.parse(headersText || "[]"),
      timeout_seconds: Number(form.get("timeout_seconds")),
      retries: Number(form.get("retries")),
    };
    await api("/api/endpoints", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("端点已保存");
    await refresh();
  } catch (error) {
    toast(error.message);
  }
});

$("#judgeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    tenant_id: form.get("tenant_id"),
    name: form.get("name"),
    provider: form.get("provider"),
    model_name: form.get("model_name"),
    base_url: form.get("base_url") || null,
    api_key: form.get("api_key") || null,
  };
  try {
    await api("/api/judges", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("裁判配置已保存");
    await refresh();
  } catch (error) {
    toast(error.message);
  }
});

$("#evaluationForm").addEventListener("input", updateConfigPreview);
$("#evaluationForm").addEventListener("change", updateConfigPreview);
$("#evaluationForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    tenant_id: form.get("tenant_id"),
    dataset_id: form.get("dataset_id"),
    endpoint_id: form.get("endpoint_id"),
    judge_id: form.get("judge_id") || null,
    concurrency: Number(form.get("concurrency")),
  };
  try {
    const run = await api("/api/evaluations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast(`评测已启动: ${run.id}`);
    await refresh();
    showView("dashboardView");
  } catch (error) {
    toast(error.message);
  }
});

document.querySelectorAll(".nav-link").forEach((link) => {
  link.addEventListener("click", () => showView(link.dataset.view));
});

$("#refreshBtn").addEventListener("click", refresh);
$("#runPicker").addEventListener("change", (event) => {
  if (event.target.value) loadReport(event.target.value);
});
$("#backToDashboard").addEventListener("click", () => showView("dashboardView"));

refresh().catch((error) => {
  renderEmptyDashboard();
  toast(error.message);
});
