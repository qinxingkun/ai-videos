import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  contentUrl,
  createJob,
  fetchHealth,
  getJob,
  listJobs,
  uploadFile,
} from "./api";
import type { ConditionIn, GpuInfo, HealthResponse, JobRecord, Mode, UploadedFile } from "./types";
import { MODE_META, PROMPT_TEMPLATES } from "./types";

const MODES = Object.keys(MODE_META) as Mode[];

type SlotKey = "first" | "last" | "refs";

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [gpus, setGpus] = useState<GpuInfo[]>([]);
  const [mode, setMode] = useState<Mode>("t2va");
  const [prompt, setPrompt] = useState(PROMPT_TEMPLATES.t2va);
  const [seed, setSeed] = useState(42);
  const shortEdge = 768;
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [duration, setDuration] = useState(5);
  const [steps, setSteps] = useState<number | "">("");
  const [flowShift, setFlowShift] = useState<number | "">("");
  const [audioFlowShift, setAudioFlowShift] = useState<number | "">("");

  const [firstFrame, setFirstFrame] = useState<UploadedFile | null>(null);
  const [lastFrame, setLastFrame] = useState<UploadedFile | null>(null);
  const [refs, setRefs] = useState<UploadedFile[]>([]);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeJob, setActiveJob] = useState<JobRecord | null>(null);
  const [history, setHistory] = useState<JobRecord[]>([]);
  const pollRef = useRef<number | null>(null);

  const meta = MODE_META[mode];
  const upstreamReady =
    meta.family === "fl2va" ? !!health?.fl2va?.ok : !!health?.ref2va?.ok;

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await fetchHealth());
    } catch (e) {
      setHealth(null);
      console.error(e);
    }
  }, []);

  useEffect(() => {
    refreshHealth();
    const t = window.setInterval(refreshHealth, 8000);
    return () => clearInterval(t);
  }, [refreshHealth]);

  useEffect(() => {
    listJobs()
      .then((r) => setHistory(r.jobs))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/api/ws/gpu`);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (Array.isArray(data.gpus)) setGpus(data.gpus);
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    setPrompt(PROMPT_TEMPLATES[mode]);
    setFirstFrame(null);
    setLastFrame(null);
    setRefs([]);
    setError(null);
  }, [mode]);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  const onUpload = async (slot: SlotKey, files: FileList | null) => {
    if (!files?.length) return;
    setError(null);
    try {
      if (slot === "first") {
        const up = await uploadFile(files[0]);
        setFirstFrame(up);
      } else if (slot === "last") {
        const up = await uploadFile(files[0]);
        setLastFrame(up);
      } else {
        const uploaded: UploadedFile[] = [];
        for (const f of Array.from(files)) {
          uploaded.push(await uploadFile(f));
        }
        setRefs((prev) => [...prev, ...uploaded]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const buildConditions = (): ConditionIn[] => {
    if (mode === "t2va") return [];
    if (mode === "i2va_first") {
      if (!firstFrame) throw new Error("请上传首帧图片");
      return [{ type: "image", uri: firstFrame.uri, role: "keyframe", frame_index: 0 }];
    }
    if (mode === "i2va_last") {
      if (!lastFrame) throw new Error("请上传尾帧图片");
      return [{ type: "image", uri: lastFrame.uri, role: "keyframe" }];
    }
    if (mode === "fl2va") {
      if (!firstFrame || !lastFrame) throw new Error("请上传首帧和尾帧图片");
      return [
        { type: "image", uri: firstFrame.uri, role: "keyframe", frame_index: 0 },
        { type: "image", uri: lastFrame.uri, role: "keyframe" },
      ];
    }
    if (!refs.length) throw new Error("请至少上传一个参考文件");
    return refs.map((r) => ({ type: r.type, uri: r.uri, role: "reference" as const }));
  };

  const startPolling = (jobId: string) => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const tick = async () => {
      try {
        const { job } = await getJob(jobId);
        setActiveJob(job);
        setHistory((prev) => {
          const rest = prev.filter((j) => j.id !== job.id);
          return [job, ...rest].slice(0, 40);
        });
        const st = (job.status || "").toLowerCase();
        if (["completed", "succeeded", "failed", "error"].includes(st)) {
          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = null;
          setBusy(false);
          if (["failed", "error"].includes(st)) {
            const msg =
              typeof job.error === "object" && job.error && "message" in (job.error as object)
                ? String((job.error as { message: string }).message)
                : JSON.stringify(job.error);
            setError(msg || "generation failed");
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setBusy(false);
        if (pollRef.current) window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    void tick();
    pollRef.current = window.setInterval(tick, 4000);
  };

  const onSubmit = async () => {
    setError(null);
    if (!upstreamReady) {
      setError(
        meta.family === "ref2va"
          ? "Ref2VA 服务未就绪（默认 :30011）。请先启动 ref2va 服务。"
          : "FL2VA 服务未就绪（默认 :30010）。",
      );
      return;
    }
    setBusy(true);
    try {
      const conditions = buildConditions();
      const { job } = await createJob({
        mode,
        prompt,
        conditions,
        seed,
        short_edge: shortEdge,
        aspect_ratio: aspectRatio,
        duration_seconds: duration,
        num_inference_steps: steps === "" ? null : Number(steps),
        flow_shift: flowShift === "" ? null : Number(flowShift),
        audio_flow_shift: audioFlowShift === "" ? null : Number(audioFlowShift),
      });
      setActiveJob(job);
      setHistory((prev) => [job, ...prev.filter((j) => j.id !== job.id)].slice(0, 40));
      startPolling(job.id);
    } catch (e) {
      setBusy(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const progressPct = useMemo(() => {
    const p = Number(activeJob?.progress ?? 0);
    if (!Number.isFinite(p)) return 0;
    return Math.max(0, Math.min(100, p));
  }, [activeJob]);

  const done =
    activeJob &&
    ["completed", "succeeded"].includes((activeJob.status || "").toLowerCase());

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>H3 Studio</h1>
          <p>MiniMax-H3 本地测试台 · FL2VA / Ref2VA · 参数可配 · GPU 实时监控</p>
        </div>
        <div className="status-row">
          <span className="pill">
            <span className={`dot ${health?.fl2va?.ok ? "ok" : "bad"}`} />
            FL2VA {health?.fl2va_url || ":30010"}
          </span>
          <span className="pill">
            <span className={`dot ${health?.ref2va?.ok ? "ok" : "bad"}`} />
            Ref2VA {health?.ref2va_url || ":30011"}
          </span>
          <button className="btn" onClick={() => void refreshHealth()}>
            刷新状态
          </button>
        </div>
      </header>

      <div className="layout">
        <aside className="panel panel-pad">
          <h2>GPU</h2>
          {gpus.length === 0 && <p className="hint">等待 GPU 数据…</p>}
          {gpus.map((g) =>
            g.error ? (
              <div className="gpu-card" key={String(g.index)}>
                <div className="gpu-head">
                  <span>GPU ?</span>
                  <span>{g.error}</span>
                </div>
              </div>
            ) : (
              <div className="gpu-card" key={g.index}>
                <div className="gpu-head">
                  <span>GPU {g.index}</span>
                  <span>{g.utilization.toFixed(0)}%</span>
                </div>
                <div className="bar">
                  <span style={{ width: `${g.utilization}%` }} />
                </div>
                <div className="bar mem">
                  <span style={{ width: `${g.memory_pct}%` }} />
                </div>
                <div className="meta">
                  <span>MEM</span>
                  <span>
                    {g.memory_used_mb.toFixed(0)} / {g.memory_total_mb.toFixed(0)} MiB
                  </span>
                  <span>TEMP</span>
                  <span>{g.temperature_c.toFixed(0)} °C</span>
                  <span>PWR</span>
                  <span>
                    {g.power_draw_w?.toFixed?.(0) ?? "—"}
                    {g.power_limit_w != null ? ` / ${g.power_limit_w.toFixed(0)}` : ""} W
                  </span>
                </div>
                <div className="hint" style={{ marginTop: 8, marginBottom: 0 }}>
                  {g.name}
                </div>
              </div>
            ),
          )}
        </aside>

        <main className="panel panel-pad">
          <h2>Generate</h2>
          <div className="modes">
            {MODES.map((m) => (
              <button
                key={m}
                className={`mode-btn ${mode === m ? "active" : ""}`}
                onClick={() => setMode(m)}
                type="button"
              >
                {MODE_META[m].label}
                <span className="sub">{MODE_META[m].family.toUpperCase()}</span>
              </button>
            ))}
          </div>
          <p className="hint">{meta.hint}</p>

          {!upstreamReady && (
            <div className="error">
              {meta.family === "ref2va"
                ? "当前模式需要 Ref2VA（:30011）。可用 h3-studio/scripts/start-minimax-h3-ref2va.sh 启动。"
                : "当前模式需要 FL2VA（:30010）。请确认服务已启动。"}
            </div>
          )}

          <div className="field">
            <label>Prompt</label>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} />
          </div>
          <div className="actions" style={{ marginTop: 0, marginBottom: 12 }}>
            <button
              className="btn"
              type="button"
              onClick={() => setPrompt(PROMPT_TEMPLATES[mode])}
            >
              重置模板
            </button>
          </div>

          {(mode === "i2va_first" || mode === "fl2va") && (
            <div className="uploads">
              <UploadSlot
                title="首帧图片"
                accept="image/*"
                onChange={(f) => void onUpload("first", f)}
                files={firstFrame ? [firstFrame] : []}
                onRemove={() => setFirstFrame(null)}
              />
            </div>
          )}
          {(mode === "i2va_last" || mode === "fl2va") && (
            <div className="uploads">
              <UploadSlot
                title="尾帧图片"
                accept="image/*"
                onChange={(f) => void onUpload("last", f)}
                files={lastFrame ? [lastFrame] : []}
                onRemove={() => setLastFrame(null)}
              />
            </div>
          )}
          {meta.family === "ref2va" && (
            <div className="uploads">
              <UploadSlot
                title="参考素材（可多选）"
                accept={
                  mode === "ref_image"
                    ? "image/*"
                    : mode === "ref_video"
                      ? "video/*"
                      : mode === "ref_audio"
                        ? "image/*,video/*,audio/*"
                        : "image/*,video/*,audio/*"
                }
                multiple
                onChange={(f) => void onUpload("refs", f)}
                files={refs}
                onRemove={(id) => setRefs((prev) => prev.filter((x) => x.id !== id))}
              />
            </div>
          )}

          <div className="grid-3">
            <div className="field">
              <label>时长 (秒)</label>
              <input
                type="number"
                min={4}
                max={15}
                step={0.5}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </div>
            <div className="field">
              <label>短边（H3 固定 768）</label>
              <input type="number" value={768} disabled />
            </div>
            <div className="field">
              <label>宽高比</label>
              <select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
                {["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "auto"].map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid-3">
            <div className="field">
              <label>Seed</label>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
              />
            </div>
            <div className="field">
              <label>Steps（可选）</label>
              <input
                type="number"
                placeholder="default"
                value={steps}
                onChange={(e) =>
                  setSteps(e.target.value === "" ? "" : Number(e.target.value))
                }
              />
            </div>
            <div className="field">
              <label>flow_shift（可选）</label>
              <input
                type="number"
                step="0.1"
                placeholder="e.g. 12"
                value={flowShift}
                onChange={(e) =>
                  setFlowShift(e.target.value === "" ? "" : Number(e.target.value))
                }
              />
            </div>
          </div>
          <div className="grid-2">
            <div className="field">
              <label>audio_flow_shift（可选）</label>
              <input
                type="number"
                step="0.1"
                placeholder="e.g. 3"
                value={audioFlowShift}
                onChange={(e) =>
                  setAudioFlowShift(e.target.value === "" ? "" : Number(e.target.value))
                }
              />
            </div>
          </div>

          <div className="actions">
            <button className="btn primary" disabled={busy} onClick={() => void onSubmit()}>
              {busy ? "生成中…" : "开始生成"}
            </button>
          </div>

          {error && <div className="error">{error}</div>}

          {activeJob && (
            <div className="result">
              <div className="row" style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>当前任务</strong>
                <span className={`badge ${activeJob.status}`}>{activeJob.status}</span>
              </div>
              <div className="hint" style={{ fontFamily: "var(--mono)" }}>
                {activeJob.id}
              </div>
              <div className="progress">
                <span style={{ width: `${progressPct}%` }} />
              </div>
              <div className="meta">
                <span>progress</span>
                <span>{progressPct}%</span>
                <span>size</span>
                <span>{activeJob.size ?? "—"}</span>
                <span>time</span>
                <span>
                  {activeJob.inference_time_s != null
                    ? `${activeJob.inference_time_s.toFixed(1)} s`
                    : "—"}
                </span>
                <span>peak mem</span>
                <span>
                  {activeJob.peak_memory_mb != null
                    ? `${activeJob.peak_memory_mb.toFixed(0)} MiB`
                    : "—"}
                </span>
              </div>
              {done && (
                <>
                  <video controls src={contentUrl(activeJob.id)} />
                  <div className="actions">
                    <a className="btn" href={contentUrl(activeJob.id)} download>
                      下载 MP4
                    </a>
                  </div>
                </>
              )}
            </div>
          )}
        </main>

        <aside className="panel panel-pad">
          <h2>History</h2>
          {history.length === 0 && <p className="hint">暂无任务</p>}
          {history.map((j) => (
            <div
              key={j.id}
              className="history-item"
              onClick={() => {
                setActiveJob(j);
                if (!["completed", "succeeded", "failed", "error"].includes(
                  (j.status || "").toLowerCase(),
                )) {
                  startPolling(j.id);
                }
              }}
            >
              <div className="id">{j.id}</div>
              <div className="row">
                <span>{MODE_META[j.mode]?.label ?? j.mode}</span>
                <span className={`badge ${j.status}`}>{j.status}</span>
              </div>
              <div className="row">
                <span>{j.upstream?.toUpperCase()}</span>
                <span>
                  {j.inference_time_s != null ? `${j.inference_time_s.toFixed(0)}s` : ""}
                </span>
              </div>
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
}

function UploadSlot(props: {
  title: string;
  accept: string;
  multiple?: boolean;
  files: UploadedFile[];
  onChange: (files: FileList | null) => void;
  onRemove: ((id?: string) => void) | (() => void);
}) {
  return (
    <div className="upload-slot">
      <strong>{props.title}</strong>
      <input
        type="file"
        accept={props.accept}
        multiple={props.multiple}
        onChange={(e) => props.onChange(e.target.files)}
      />
      <div className="file-list">
        {props.files.map((f) => (
          <div className="file-item" key={f.id}>
            <span>
              [{f.type}] {f.filename}
            </span>
            <button
              type="button"
              onClick={() => {
                // support both signatures
                (props.onRemove as (id?: string) => void)(f.id);
              }}
            >
              移除
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
