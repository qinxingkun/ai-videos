#!/usr/bin/env bash
# AI 短剧场景批量测试：>=10 个场景，每个成片 >=15 秒
# 策略：每场景 3 段 x 121 帧 (24fps, 约 5.04s/段) -> 拼接后约 15.1 秒
set -eu
set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CKPT_DIR="${CKPT_DIR:-/mnt/ddr2/qxk/models/Wan2.2-TI2V-5B}"
OUT_DIR="${OUT_DIR:-$ROOT/outputs/short_drama_$(date +%Y%m%d_%H%M%S)}"
LOG_FILE="$OUT_DIR/batch.log"
FRAME_NUM="${FRAME_NUM:-121}"
FPS=24
CLIPS_PER_SCENE=3
MIN_DURATION=$((CLIPS_PER_SCENE * FRAME_NUM / FPS))

mkdir -p "$OUT_DIR/clips" "$OUT_DIR/final"

export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

gen_clip() {
  local save_file="$1"
  local prompt="$2"
  local seed="$3"
  log "  生成片段: $(basename "$save_file") (seed=$seed)"
  python generate.py \
    --task ti2v-5B \
    --size 1280*704 \
    --ckpt_dir "$CKPT_DIR" \
    --offload_model True \
    --convert_model_dtype \
    --t5_cpu \
    --frame_num "$FRAME_NUM" \
    --base_seed "$seed" \
    --save_file "$save_file" \
    --prompt "$prompt"
}

merge_scene() {
  local scene_id="$1"
  local final_file="$OUT_DIR/final/scene_${scene_id}.mp4"
  local list_file="$OUT_DIR/clips/scene_${scene_id}_concat.txt"
  : > "$list_file"
  for i in 1 2 3; do
    echo "file '$(realpath "$OUT_DIR/clips/scene_${scene_id}_part${i}.mp4")'" >> "$list_file"
  done
  ffmpeg -y -f concat -safe 0 -i "$list_file" -c copy "$final_file" >> "$LOG_FILE" 2>&1
  local duration
  duration=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$final_file")
  log "  成片: $final_file (${duration}s)"
}

# id|标题|prompt
read -r -d '' SCENES << 'EOF' || true
01|雨夜重逢|Cinematic short drama, rainy neon city street at night, a young woman in a beige trench coat stops under a streetlight, a man with an umbrella slowly walks toward her, emotional reunion, wet pavement reflections, moody blue-orange lighting, shallow depth of field, smooth camera dolly in, live-action film look, no subtitles
02|宫廷密谋|Chinese palace short drama, dim imperial hall with red pillars and candlelight, a consort in elegant hanfu whispers to a loyal maid, suspenseful atmosphere, slow tracking shot, silk robes flowing, golden bokeh, cinematic historical drama style, no subtitles
03|档案室悬疑|Mystery short drama, dusty archive room, a detective in a dark coat pulls a folder from a metal shelf, beam of flashlight cuts through floating dust, tense mood, handheld camera subtle movement, noir lighting, no subtitles
04|毕业告别|Youth campus short drama, golden hour school playground, students in uniforms hug and laugh, cherry blossom petals drifting, warm sunset backlight, gentle pan across smiling faces, nostalgic tone, no subtitles
05|会议室对峙|Workplace short drama, modern glass conference room, two executives in suits argue across a long table, city skyline behind blinds, sharp contrast lighting, tense eye contact, slow push-in shot, no subtitles
06|御剑云海|Xianxia short drama, hero in white robes rides a sword above rolling sea of clouds at sunrise, long hair flowing in wind, epic wide aerial shot transitioning to medium follow shot, mystical atmosphere, no subtitles
07|民国弄堂|Republic-era short drama, narrow Shanghai alley with laundry lines and vintage signs, a rickshaw passes under warm lantern light, pedestrians in qipao and fedoras, nostalgic film grain, smooth tracking shot, no subtitles
08|舱外维修|Sci-fi short drama, astronaut in white EVA suit repairs a space station module, Earth curvature in background, cold blue lighting, slow orbital camera move, realistic zero-gravity motion, no subtitles
09|厨房温情|Family short drama, cozy kitchen at dawn, grandmother wraps dumplings while a child watches, steam rising from a pot, soft window light, intimate close-ups and warm colors, no subtitles
10|市场追逐|Action short drama, bustling outdoor market, a runner weaves through vendors and colorful stalls, dynamic follow cam, crates knocked aside, high energy daylight, cinematic motion blur, no subtitles
11|急诊抢救|Medical short drama, emergency room, doctors and nurses rush a gurney through sliding doors, monitors beeping, harsh fluorescent light mixed with red alarm glow, urgent handheld camera, no subtitles
12|咖啡馆偶遇|Romance short drama, rainy afternoon cafe interior, two strangers reach for the same book on a shelf, eyes meet, soft jazz ambience implied, warm window light and bokeh, gentle zoom, no subtitles
EOF

log "========== AI 短剧批量测试开始 =========="
log "输出目录: $OUT_DIR"
log "每场景 ${CLIPS_PER_SCENE} 段 x ${FRAME_NUM} 帧 @ ${FPS}fps, 目标时长 >= ${MIN_DURATION}s"
log "模型: $CKPT_DIR"

scene_count=0
ok_count=0
fail_count=0

while IFS='|' read -r scene_id title prompt; do
  [[ -z "${scene_id:-}" ]] && continue
  scene_count=$((scene_count + 1))
  log ""
  log ">>> 场景 ${scene_id}: ${title}"

  scene_ok=true
  base_seed=$((10000 + 10#${scene_id} * 1000))

  for part in 1 2 3; do
    clip_file="$OUT_DIR/clips/scene_${scene_id}_part${part}.mp4"
    part_prompt="${prompt}, continuous scene part ${part} of 3, consistent characters and lighting"
    seed=$((base_seed + part))
    if ! gen_clip "$clip_file" "$part_prompt" "$seed"; then
      log "  [FAIL] 片段生成失败: scene_${scene_id}_part${part}"
      scene_ok=false
      break
    fi
  done

  if $scene_ok; then
    if merge_scene "$scene_id"; then
      ok_count=$((ok_count + 1))
      echo "${scene_id}|${title}|ok|$OUT_DIR/final/scene_${scene_id}.mp4" >> "$OUT_DIR/results.tsv"
    else
      fail_count=$((fail_count + 1))
      echo "${scene_id}|${title}|merge_fail|" >> "$OUT_DIR/results.tsv"
    fi
  else
    fail_count=$((fail_count + 1))
    echo "${scene_id}|${title}|gen_fail|" >> "$OUT_DIR/results.tsv"
  fi
done <<< "$SCENES"

log ""
log "========== 批量测试结束 =========="
log "场景总数: ${scene_count}, 成功: ${ok_count}, 失败: ${fail_count}"
log "结果清单: $OUT_DIR/results.tsv"
log "成片目录: $OUT_DIR/final/"
