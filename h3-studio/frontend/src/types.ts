export type Mode =
  | "t2va"
  | "i2va_first"
  | "i2va_last"
  | "fl2va"
  | "ref_image"
  | "ref_video"
  | "ref_audio"
  | "ref_mixed";

export type MediaType = "image" | "video" | "audio";

export interface UploadedFile {
  id: string;
  filename: string;
  type: MediaType;
  uri: string;
  url: string;
  path: string;
}

export interface ConditionIn {
  type: MediaType;
  uri: string;
  role: "keyframe" | "reference";
  frame_index?: number | null;
}

export interface JobRecord {
  id: string;
  mode: Mode;
  upstream: string;
  task: string;
  status: string;
  progress?: number | null;
  created_at?: number | null;
  size?: string | null;
  seconds?: string | number | null;
  inference_time_s?: number | null;
  peak_memory_mb?: number | null;
  error?: unknown;
  file_path?: string | null;
  prompt?: string | null;
}

export interface GpuInfo {
  index: number;
  name: string;
  utilization: number;
  memory_used_mb: number;
  memory_total_mb: number;
  memory_pct: number;
  temperature_c: number;
  power_draw_w?: number | null;
  power_limit_w?: number | null;
  error?: string;
}

export interface HealthResponse {
  ok: boolean;
  fl2va: { ok: boolean; url?: string; error?: string };
  ref2va: { ok: boolean; url?: string; error?: string };
  fl2va_url: string;
  ref2va_url: string;
}

export const MODE_META: Record<
  Mode,
  { label: string; family: "fl2va" | "ref2va"; hint: string }
> = {
  t2va: { label: "文生视频", family: "fl2va", hint: "仅文本提示词" },
  i2va_first: { label: "首帧生视频", family: "fl2va", hint: "上传一张首帧图" },
  i2va_last: { label: "尾帧生视频", family: "fl2va", hint: "上传一张尾帧图" },
  fl2va: { label: "首尾帧生视频", family: "fl2va", hint: "上传首帧 + 尾帧" },
  ref_image: { label: "参考图生视频", family: "ref2va", hint: "最多 9 张参考图" },
  ref_video: { label: "参考视频生视频", family: "ref2va", hint: "最多 3 段参考视频" },
  ref_audio: { label: "参考语音生视频", family: "ref2va", hint: "音频 + 图/视频" },
  ref_mixed: { label: "混合参考", family: "ref2va", hint: "图/视频/音频混合，最多 12 个" },
};

export const PROMPT_TEMPLATES: Record<Mode, string> = {
  t2va:
    "一只橘猫在阳光下的窗台打哈欠，电影感，浅景深，温暖色调，细腻毛发质感。",
  i2va_first:
    "以首帧图像为起点，镜头缓慢推进，人物自然眨眼并轻微转头，光影柔和变化，电影质感。",
  i2va_last:
    "生成一段自然过渡到尾帧图像的视频，中间动作连贯，光影与构图平滑衔接。",
  fl2va:
    "从首帧平滑过渡到尾帧，主体动作自然连贯，镜头稳定，细节保持一致。",
  ref_image:
    "subject_definitions:\n<Picture 1> is the visual identity reference.\n\nsummary:\nGenerate a short cinematic clip that preserves the identity and style of <Picture 1>.",
  ref_video:
    "subject_definitions:\n<Video 1> is the source/reference video.\n\nsummary:\nGenerate a target video guided by the motion and appearance in <Video 1>.",
  ref_audio:
    "subject_definitions:\n<Audio 1> is the voice/timbre reference.\n<Picture 1> is the visual reference.\n\nsummary:\nGenerate a speaking shot that matches the visual reference and the voice timbre of <Audio 1>.",
  ref_mixed:
    "subject_definitions:\nDefine subjects for each uploaded reference.\n\nsummary:\nGenerate a multimodal reference-driven clip that respects image/video/audio references.",
};
