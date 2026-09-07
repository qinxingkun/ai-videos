import type { ConditionIn, HealthResponse, JobRecord, Mode, UploadedFile } from "./types";

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail?.message) return String(data.detail.message);
    return JSON.stringify(data);
  } catch {
    return await res.text();
  }
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function uploadFile(file: File): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/uploads", { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export interface CreateJobBody {
  mode: Mode;
  prompt: string;
  conditions: ConditionIn[];
  seed: number;
  short_edge: number;
  aspect_ratio: string;
  duration_seconds: number;
  num_inference_steps?: number | null;
  flow_shift?: number | null;
  audio_flow_shift?: number | null;
}

export async function createJob(body: CreateJobBody): Promise<{
  job: JobRecord;
  upstream_response: unknown;
}> {
  const res = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getJob(id: string): Promise<{ job: JobRecord }> {
  const res = await fetch(`/api/jobs/${id}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function listJobs(): Promise<{ jobs: JobRecord[] }> {
  const res = await fetch("/api/jobs");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export function contentUrl(id: string): string {
  return `/api/jobs/${id}/content`;
}
