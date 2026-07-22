# AI 短剧批量测试说明

## 目标

- 场景数：**12 个**（>= 10）
- 每段成片时长：**>= 15 秒**（3 x 121 帧 @ 24fps ≈ 15.1 秒）
- 模型：`Wan2.2-TI2V-5B` 文生视频

## 运行

```bash
conda activate wan
cd /mnt/ddr2/qxk/workspace/ai-videos/Wan2.2
chmod +x scripts/short_drama_batch.sh
bash scripts/short_drama_batch.sh
```

后台运行：

```bash
nohup bash scripts/short_drama_batch.sh > outputs/short_drama_nohup.log 2>&1 &
```

## 输出结构

```
outputs/short_drama_YYYYMMDD_HHMMSS/
├── batch.log          # 运行日志
├── results.tsv        # 场景结果汇总
├── clips/             # 每场景 3 个片段
└── final/             # 拼接后的成片 (scene_01.mp4 ...)
```

## 场景列表

| ID | 标题 | 类型 |
|----|------|------|
| 01 | 雨夜重逢 | 都市爱情 |
| 02 | 宫廷密谋 | 古装悬疑 |
| 03 | 档案室悬疑 | 推理 |
| 04 | 毕业告别 | 青春 |
| 05 | 会议室对峙 | 职场 |
| 06 | 御剑云海 | 仙侠 |
| 07 | 民国弄堂 | 年代 |
| 08 | 舱外维修 | 科幻 |
| 09 | 厨房温情 | 家庭 |
| 10 | 市场追逐 | 动作 |
| 11 | 急诊抢救 | 医疗 |
| 12 | 咖啡馆偶遇 | 爱情 |

## 预估耗时

- 单片段（121 帧）：约 3–4 分钟
- 单场景（3 片段 + 拼接）：约 10–15 分钟
- 全部 12 场景：约 **2–3 小时**

## 显存

使用已验证参数：`--offload_model True --convert_model_dtype --t5_cpu --frame_num 121`

若 OOM，请先释放 GPU 0 上 vLLM 占用，或降低并发。
