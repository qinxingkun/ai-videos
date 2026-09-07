const MODE_META = {
  t2va: { label: "文生", family: "fl2va", hint: "纯文本生成视频+音频" },
  i2va_first: { label: "首帧", family: "fl2va", hint: "上传首帧图片引导生成" },
  i2va_last: { label: "尾帧", family: "fl2va", hint: "上传尾帧图片引导生成" },
  fl2va: { label: "首尾帧", family: "fl2va", hint: "首帧+尾帧插值生成" },
  ref_image: { label: "参考图", family: "ref2va", hint: "1–9 张参考图（需 Ref2VA）" },
  ref_video: { label: "参考视频", family: "ref2va", hint: "1–3 段参考视频（需 Ref2VA）" },
  ref_audio: { label: "参考语音", family: "ref2va", hint: "音频+画面参考（需 Ref2VA）" },
  ref_mixed: { label: "混合参考", family: "ref2va", hint: "图/视频/音频混合（需 Ref2VA）" },
};

const PROMPTS = {
  t2va: "A cinematic shot of a red balloon drifting across a clear blue sky, soft sunlight, gentle camera drift.",
  i2va_first: "Continue from the first frame with natural motion and consistent lighting.",
  i2va_last: "Animate toward the last frame with smooth motion and matching style.",
  fl2va: "Transition smoothly from the first frame to the last frame.",
  ref_image: "Generate a video matching the reference image identity and style.",
  ref_video: "Follow the motion and appearance of the reference video.",
  ref_audio: "Sync motion to the reference audio while keeping visual consistency.",
  ref_mixed: "Combine reference image/video/audio cues into one coherent clip.",
};

const state = {
  mode: "t2va",
  health: null,
  gpus: [],
  first: null,
  last: null,
  refs: [],
  active: null,
  history: [],
  busy: false,
  error: null,
  pollTimer: null,
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detail = data.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : detail?.message || JSON.stringify(detail || data);
    throw new Error(msg || `HTTP ${r.status}`);
  }
  return data;
}

async function refreshHealth() {
  try {
    state.health = await api("/api/health");
  } catch {
    state.health = null;
  }
  renderStatus();
}

async function refreshHistory() {
  try {
    const data = await api("/api/jobs");
    state.history = data.jobs || [];
  } catch {
    /* ignore */
  }
  renderHistory();
}

function connectGpuWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/ws/gpu`);
  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (Array.isArray(data.gpus)) {
        state.gpus = data.gpus;
        renderGpus();
      }
    } catch {
      /* ignore */
    }
  };
  ws.onclose = () => setTimeout(connectGpuWs, 2000);
}

async function upload(file) {
  const fd = new FormData();
  fd.append("file", file);
  return api("/api/uploads", { method: "POST", body: fd });
}

function buildConditions() {
  const m = state.mode;
  if (m === "t2va") return [];
  if (m === "i2va_first") {
    if (!state.first) throw new Error("请上传首帧图片");
    return [{ type: "image", uri: state.first.uri, role: "keyframe", frame_index: 0 }];
  }
  if (m === "i2va_last") {
    if (!state.last) throw new Error("请上传尾帧图片");
    return [{ type: "image", uri: state.last.uri, role: "keyframe" }];
  }
  if (m === "fl2va") {
    if (!state.first || !state.last) throw new Error("请上传首帧和尾帧");
    return [
      { type: "image", uri: state.first.uri, role: "keyframe", frame_index: 0 },
      { type: "image", uri: state.last.uri, role: "keyframe" },
    ];
  }
  if (!state.refs.length) throw new Error("请上传参考素材");
  return state.refs.map((f) => ({ type: f.type, uri: f.uri, role: "reference" }));
}

async function submit() {
  state.error = null;
  state.busy = true;
  renderForm();
  try {
    const steps = $("#steps").value;
    const body = {
      mode: state.mode,
      prompt: $("#prompt").value.trim(),
      conditions: buildConditions(),
      seed: Number($("#seed").value) || 42,
      short_edge: 768,
      aspect_ratio: $("#aspect").value,
      duration_seconds: Number($("#duration").value) || 5,
    };
    if (steps !== "") body.num_inference_steps = Number(steps);
    const data = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    state.active = data.job;
    startPoll(data.job.id);
    await refreshHistory();
  } catch (e) {
    state.error = e.message || String(e);
  } finally {
    state.busy = false;
    renderForm();
    renderActive();
  }
}

function startPoll(id) {
  if (state.pollTimer) clearInterval(state.pollTimer);
  const tick = async () => {
    try {
      const data = await api(`/api/jobs/${id}`);
      state.active = data.job;
      renderActive();
      const st = (data.job.status || "").toLowerCase();
      if (["completed", "succeeded", "failed", "error"].includes(st)) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        await refreshHistory();
      }
    } catch (e) {
      state.error = e.message || String(e);
      renderForm();
    }
  };
  tick();
  state.pollTimer = setInterval(tick, 2000);
}

function renderStatus() {
  const h = state.health;
  $("#fl2va-dot").className = `dot ${h?.fl2va?.ok ? "ok" : "bad"}`;
  $("#ref2va-dot").className = `dot ${h?.ref2va?.ok ? "ok" : "bad"}`;
  $("#fl2va-label").textContent = `FL2VA ${h?.fl2va_url || ":30010"}`;
  $("#ref2va-label").textContent = `Ref2VA ${h?.ref2va_url || ":30011"}`;
}

function renderGpus() {
  const box = $("#gpus");
  box.innerHTML = "";
  if (!state.gpus.length) {
    box.append(el("p", "hint", "等待 GPU 数据…"));
    return;
  }
  for (const g of state.gpus) {
    if (g.error) {
      const card = el("div", "gpu-card");
      card.append(el("div", "gpu-head", `GPU ? · ${g.error}`));
      box.append(card);
      continue;
    }
    const card = el("div", "gpu-card");
    const head = el("div", "gpu-head");
    head.append(el("span", null, `GPU ${g.index}`), el("span", null, `${g.utilization.toFixed(0)}%`));
    card.append(head);
    const util = el("div", "bar");
    util.append(el("span"));
    util.querySelector("span").style.width = `${g.utilization}%`;
    const mem = el("div", "bar mem");
    mem.append(el("span"));
    mem.querySelector("span").style.width = `${g.memory_pct}%`;
    card.append(util, mem);
    const meta = el("div", "meta");
    meta.innerHTML = `<span>MEM</span><span>${g.memory_used_mb.toFixed(0)} / ${g.memory_total_mb.toFixed(0)} MiB</span>
      <span>TEMP</span><span>${g.temperature_c.toFixed(0)} °C</span>
      <span>PWR</span><span>${g.power_draw_w?.toFixed?.(0) ?? "—"} / ${g.power_limit_w?.toFixed?.(0) ?? "—"} W</span>`;
    card.append(meta, el("div", "hint", g.name));
    box.append(card);
  }
}

function renderModes() {
  const box = $("#modes");
  box.innerHTML = "";
  for (const [key, meta] of Object.entries(MODE_META)) {
    const btn = el("button", `mode-btn${state.mode === key ? " active" : ""}`);
    btn.type = "button";
    btn.innerHTML = `${meta.label}<span class="sub">${meta.family.toUpperCase()}</span>`;
    btn.onclick = () => {
      state.mode = key;
      state.first = state.last = null;
      state.refs = [];
      state.error = null;
      $("#prompt").value = PROMPTS[key];
      renderModes();
      renderForm();
    };
    box.append(btn);
  }
}

function fileChip(f, onRemove) {
  const chip = el("div", "file-chip");
  chip.append(el("span", null, f.filename || f.id));
  const rm = el("button", "btn", "×");
  rm.type = "button";
  rm.onclick = onRemove;
  chip.append(rm);
  return chip;
}

function renderUploads() {
  const box = $("#uploads");
  box.innerHTML = "";
  const m = state.mode;
  const meta = MODE_META[m];
  const addSlot = (title, accept, multiple, files, onFiles, onRemove) => {
    const slot = el("div", "upload-slot");
    slot.append(el("h3", null, title));
    const input = el("input");
    input.type = "file";
    input.accept = accept;
    if (multiple) input.multiple = true;
    input.onchange = async () => {
      try {
        await onFiles(input.files);
      } catch (e) {
        state.error = e.message || String(e);
        renderForm();
      }
    };
    slot.append(input);
    for (const f of files) slot.append(fileChip(f, () => onRemove(f.id)));
    box.append(slot);
  };

  if (m === "i2va_first" || m === "fl2va") {
    addSlot(
      "首帧图片",
      "image/*",
      false,
      state.first ? [state.first] : [],
      async (files) => {
        if (files?.[0]) state.first = await upload(files[0]);
        renderUploads();
      },
      () => {
        state.first = null;
        renderUploads();
      },
    );
  }
  if (m === "i2va_last" || m === "fl2va") {
    addSlot(
      "尾帧图片",
      "image/*",
      false,
      state.last ? [state.last] : [],
      async (files) => {
        if (files?.[0]) state.last = await upload(files[0]);
        renderUploads();
      },
      () => {
        state.last = null;
        renderUploads();
      },
    );
  }
  if (meta.family === "ref2va") {
    const accept =
      m === "ref_image" ? "image/*" : m === "ref_video" ? "video/*" : "image/*,video/*,audio/*";
    addSlot(
      "参考素材（可多选）",
      accept,
      true,
      state.refs,
      async (files) => {
        for (const f of Array.from(files || [])) state.refs.push(await upload(f));
        renderUploads();
      },
      (id) => {
        state.refs = state.refs.filter((x) => x.id !== id);
        renderUploads();
      },
    );
  }
}

function renderForm() {
  const meta = MODE_META[state.mode];
  $("#mode-hint").textContent = meta.hint;
  const ready = meta.family === "fl2va" ? !!state.health?.fl2va?.ok : !!state.health?.ref2va?.ok;
  const warn = $("#upstream-warn");
  if (!ready) {
    warn.hidden = false;
    warn.textContent =
      meta.family === "ref2va"
        ? "当前模式需要 Ref2VA（:30011）。可用 h3-studio/scripts/start-minimax-h3-ref2va.sh 启动。"
        : "当前模式需要 FL2VA（:30010）。请确认服务已启动。";
  } else {
    warn.hidden = true;
  }
  const err = $("#error");
  if (state.error) {
    err.hidden = false;
    err.textContent = state.error;
  } else {
    err.hidden = true;
  }
  $("#submit").disabled = state.busy || !ready;
  $("#submit").textContent = state.busy ? "提交中…" : "开始生成";
  renderUploads();
}

function renderActive() {
  const box = $("#active");
  const j = state.active;
  if (!j) {
    box.innerHTML = `<p class="hint">尚未提交任务</p>`;
    return;
  }
  const pct = Math.max(0, Math.min(100, Number(j.progress || 0)));
  box.innerHTML = `
    <div class="progress">
      <div class="bar"><span style="width:${pct}%"></span></div>
    </div>
    <div class="job-meta">
      <span>ID</span><span style="font-family:var(--mono)">${j.id}</span>
      <span>状态</span><span>${j.status} · ${pct}%</span>
      <span>模式</span><span>${j.mode} / ${j.task}</span>
      <span>尺寸</span><span>${j.size || "—"} · ${j.seconds || "—"}s</span>
      <span>耗时</span><span>${j.inference_time_s != null ? j.inference_time_s.toFixed(1) + "s" : "—"}</span>
      <span>峰值显存</span><span>${j.peak_memory_mb != null ? j.peak_memory_mb.toFixed(0) + " MiB" : "—"}</span>
    </div>`;
  const st = (j.status || "").toLowerCase();
  if (["completed", "succeeded"].includes(st)) {
    const v = el("video");
    v.controls = true;
    v.src = `/api/jobs/${j.id}/content?t=${Date.now()}`;
    box.append(v);
  }
  if (j.error) {
    const e = el("div", "error", typeof j.error === "string" ? j.error : JSON.stringify(j.error));
    box.append(e);
  }
}

function renderHistory() {
  const box = $("#history");
  box.innerHTML = "";
  if (!state.history.length) {
    box.append(el("p", "hint", "暂无历史"));
    return;
  }
  for (const j of state.history) {
    const btn = el("button", `history-item${state.active?.id === j.id ? " active" : ""}`);
    btn.type = "button";
    btn.innerHTML = `<div>${j.mode} · ${j.status}</div><div class="id">${j.id}</div>`;
    btn.onclick = () => {
      state.active = j;
      startPoll(j.id);
      renderHistory();
    };
    box.append(btn);
  }
}

function init() {
  $("#prompt").value = PROMPTS.t2va;
  $("#refresh").onclick = () => void refreshHealth();
  $("#reset-prompt").onclick = () => {
    $("#prompt").value = PROMPTS[state.mode];
  };
  $("#submit").onclick = () => void submit();
  renderModes();
  renderForm();
  renderGpus();
  renderActive();
  refreshHealth();
  refreshHistory();
  connectGpuWs();
  setInterval(refreshHealth, 8000);
}

init();
