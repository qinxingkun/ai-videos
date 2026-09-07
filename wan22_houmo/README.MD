# Wan2.2

本示例展示如何将 Wan2.2 A14B 文生视频（T2V）和图生视频（I2V）模型量化、编译，并部署到后摩芯片设备上运行。

[TOC]

## 1 模型说明

本示例包含 Wan2.2 A14B 的两个任务模型。Wan2.2 使用双 DiT Expert MoE：高噪声阶段使用 high-noise expert，低噪声阶段使用 low-noise expert；每个采样 step 由 host 侧 scheduler/CFG 逻辑选择对应 expert。

### 预训练模型

#### Wan2.2 T2V-A14B

- 模型名称: Wan2.2-T2V-A14B
- 来源: [https://www.modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged](https://www.modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged)
- 许可: Apache License 2.0（Comfy-Org 仓库元数据声明；上游许可见 [Wan2.2 LICENSE.txt](https://github.com/Wan-Video/Wan2.2/blob/main/LICENSE.txt)）

#### Wan2.2 I2V-A14B

- 模型名称: Wan2.2-I2V-A14B
- 来源: [https://www.modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged](https://www.modelscope.cn/models/Comfy-Org/Wan_2.2_ComfyUI_Repackaged)
- 许可: Apache License 2.0（Comfy-Org 仓库元数据声明；上游许可见 [Wan2.2 LICENSE.txt](https://github.com/Wan-Video/Wan2.2/blob/main/LICENSE.txt)）

模型实现和推理源码来自 [Wan-Video/Wan2.2](https://github.com/Wan-Video/Wan2.2)。

预训练模型在运行时下载，工程发布**不包含**模型权重。

当前量化流程主要使用 `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` 中的重打包权重；该仓库 README 元数据声明其许可为 Apache License 2.0。`config.yaml` 中对应的 Wan-AI T2V/I2V 仓库作为任务相关补充资源，用于下载 tokenizer 等文件，并不改变主要权重来源说明。

`Comfy-Org/Wan_2.2_ComfyUI_Repackaged` 是多个上游模型、LoRA 和辅助文件的重打包集合。虽然仓库元数据声明为 Apache License 2.0，但其中不同文件仍可能受各自上游项目许可证和使用条款约束；使用或再分发相关文件时，应分别核对对应上游仓库的许可要求。

本例只适用于xh2。

### 默认配置

当前目录使用 `config.yaml` 作为默认值单一真值来源。当前默认模型为：

- `model_name=wan2.2`
- `model_size=i2v-a14b`
- `ncore=2`
- `ndevice=1`
- `video_width=480`
- `video_height=832`
- `quant_type=w8a8`

当前示例包含以下子模型：

- `t5`: T5 文本编码器 HMM；
- `vae_encode`: I2V 图像/视频条件编码器 HMM，仅 I2V 使用；
- `vae_decode`: 将最终 latent 解码为视频；
- `low_noise_model`: 低噪声阶段 DiT Expert；
- `high_noise_model`: 高噪声阶段 DiT Expert。

### 资源要求

**后摩设备运行要求：**

- `wan2.2-i2v-a14b`: 双卡 2*48GB 可运行；
- `wan2.2-t2v-a14b`: 双卡 2*48GB 可运行。

**量化硬件要求：**

- `wan2.2-i2v-a14b`: 需要 GPU，显存最小 48GB；
- `wan2.2-t2v-a14b`: 需要 GPU，显存最小 48GB。

**编译时 host 内存要求：**

- `wan2.2-i2v-a14b`: 需要空闲 host 内存最小 170GB；
- `wan2.2-t2v-a14b`: 需要空闲 host 内存最小 170GB。

## 2 快速开始

Wan2.2 当前提供 Python 脚本量化、编译和推理流程。芯片模型只能在 Linux 环境下量化和编译。

### 2.1 环境准备

设置目标平台：

```bash
export HOUMO_TARGET=xh2
```

安装示例所需依赖，建议使用虚拟环境：

```bash
pip3 install -r requirements.txt
```

目录中包含 Wan2.2 原始源码目录 `Wan2.2-main/`。`demo.py` 会从该目录加载 Wan 配置、tokenizer 和 scheduler 模块。

### 2.2 获取模型和数据

`get_model.py` 根据 `config.yaml` 中的 `model_name` 和 `model_size` 读取 ModelScope 仓库配置。

下载原始 I2V 模型，用于后续 LoRA 合并和量化：

```bash
python3 get_model.py --type raw --model_name wan2.2 --model_size i2v-a14b
```

下载 T2V 原始模型：

```bash
python3 get_model.py --type raw --model_name wan2.2 --model_size t2v-a14b
```

如果只需要运行已有的芯片模型，可下载预编译 HMM：

```bash
python3 get_model.py --type hmm --model_name wan2.2 --model_size i2v-a14b
```

`get_model.py` 的 raw 下载会将第二个 ModelScope 仓库中的 `google` tokenizer 目录复制到第一个仓库目录，以便后续 PTQ 和 demo 共用完整的模型目录结构。

### 2.3 量化

量化需要 GPU，并要求宿主机安装与 CUDA 12.8 兼容的 CUDA 和驱动。启动 docker 时将 GPU 映射到容器内，参考命令：

```bash
docker run -it --gpus all --pid=host -w /hmdd -v $PWD:/hmdd --shm-size 64g harbor.houmo.ai/toolchain/release:Dadao-xh2-x.y.z-ubuntu24.04-x86.64 /bin/bash
```

进入 docker 后设置环境变量，进入当前模型目录并执行 PTQ：

```bash
source env.sh
cd models/media_gen/wan2.2
python3 ptq.py --model_name wan2.2 --model_size i2v-a14b
```

T2V 量化命令为：

```bash
python3 ptq.py --model_name wan2.2 --model_size t2v-a14b
```

`ptq.py` 默认从配置对应的第一个 `modelscope_repo` 推导输入模型目录，默认输出到：

```text
output/${HOUMO_TARGET}/hmquant_i2v-a14b/
output/${HOUMO_TARGET}/hmquant_t2v-a14b/
```

量化导出完成后，脚本还会将：

```text
<model_dir>/google/umt5-xxl
```

复制为：

```text
<output_dir>/hf_config
```

该目录供 `demo.py` 使用。LoRA 合并权重保存在原始模型目录的 `merged/` 下；I2V 和 T2V 通过 adapter 文件名中的 task 信息区分。

### 2.4 编译

`build.py` 默认从与 `model_size` 对应的量化目录读取 HMONNX，并将 HMM 输出到 `output/${HOUMO_TARGET}`：

```bash
python3 build.py --model_name wan2.2 --model_size i2v-a14b
```

T2V 编译命令为：

```bash
python3 build.py --model_name wan2.2 --model_size t2v-a14b
```

不传 `--model_dir` 时，默认读取：

```text
output/${HOUMO_TARGET}/hmquant_i2v-a14b
output/${HOUMO_TARGET}/hmquant_t2v-a14b
```

默认输出文件名分别为：

- `wan2.2-i2v-a14b_t5.hmm`
- `wan2.2-i2v-a14b_vae_encode.hmm`
- `wan2.2-i2v-a14b_vae_decode.hmm`
- `wan2.2-i2v-a14b_low_noise.hmm`
- `wan2.2-i2v-a14b_high_noise.hmm`

T2V 不需要 `vae_encode`，因此正常 T2V 流程只会使用：

- `wan2.2-t2v-a14b_t5.hmm`
- `wan2.2-t2v-a14b_vae_decode.hmm`
- `wan2.2-t2v-a14b_low_noise.hmm`
- `wan2.2-t2v-a14b_high_noise.hmm`

### 2.5 演示

`demo.py` 通过 `config.yaml`、`model_name` 和 `model_size` 推导默认路径，不再需要用户传入 `--task`。例如：

执行 demo 前需要配置环境变量设置 HMM 推理时间：

```bash
export HDPL_API_TIMEOUT=300000000
```

```bash
python3 demo.py --model_name wan2.2 --model_size i2v-a14b
```

T2V 演示：

```bash
python3 demo.py --model_name wan2.2 --model_size t2v-a14b
```

I2V 可显式指定输入图片和 prompt：

```bash
python3 demo.py \
  --model_name wan2.2 \
  --model_size i2v-a14b \
  --image <自定义图片路径> \
  --prompt "自定义prompt"
```

默认输出文件名由 `model_size` 生成：

```text
wan2.2-i2v-a14b_demo.mp4
wan2.2-t2v-a14b_demo.mp4
```

`--output` 可覆盖默认文件名。`demo.py` 默认从以下位置读取 HMM 和 demo 依赖：

```text
output/${HOUMO_TARGET}/wan2.2-<model_size>_*.hmm
output/${HOUMO_TARGET}/hmquant_<model_size>/quant_embedding.pt
output/${HOUMO_TARGET}/hmquant_<model_size>/low_noise_timestep_embedding.pt
output/${HOUMO_TARGET}/hmquant_<model_size>/high_noise_timestep_embedding.pt
output/${HOUMO_TARGET}/hmquant_<model_size>/hf_config/
```

T2V 不会加载或执行 `vae_encode`；I2V 会额外加载 `vae_encode` 并将输入图像编码为扩散条件。

`demo.py` 执行结束后始终打印 `PerfTracker` 性能摘要，包括模型加载、T5、VAE、DiT、采样 step、视频保存等 scope。

## 3 一键评估

以上流程可以通过当前目录的 `test.sh` 执行。默认执行 demo 步骤：

```bash
# 默认执行 demo，会下载预编译模型
bash test.sh

# 完整流程：下载原始模型、量化、编译、演示
bash test.sh -s all
```

`test.sh` 当前实际支持并消费的参数包括：

```text
Usage: test.sh [options]
  -s, --step              Step to run. Default: demo. Choices: demo, build, quant, all.
  -size, --model_size     Model size.
  -name, --model_name     Model name.
  --skip_download         Skip model download steps.
  -h, --help              Show this help message.
```

Wan2.2 当前使用的 `model_size` 为：

```text
i2v-a14b
t2v-a14b
```

示例：

```bash
# 仅量化 I2V
bash test.sh -s quant -name wan2.2 -size i2v-a14b

# 仅编译 T2V，要求已有对应量化产物
bash test.sh -s build -name wan2.2 -size t2v-a14b

# 仅演示 I2V，跳过下载
bash test.sh -s demo -name wan2.2 -size i2v-a14b --skip_download

# 完整执行 T2V 流程
bash test.sh -s all -name wan2.2 -size t2v-a14b
```

## 4 参考结果

### 4.1 i2v 演示结果

```bash
[HMM] Component device mapping:
  t5: device 0
  vae_decode: device 1
  low_noise_model: device 1
  high_noise_model: device 0
  vae_encode: device 1
[HMM] Loaded component=t5 device=0 model=./output/xh2/wan2.2-i2v-a14b_t5.hmm
[HMM] Loaded component=vae_decode device=1 model=./output/xh2/wan2.2-i2v-a14b_vae_decode.hmm
[HMM] Loaded component=low_noise_model device=1 model=./output/xh2/wan2.2-i2v-a14b_low_noise.hmm
[HMM] Loaded component=high_noise_model device=0 model=./output/xh2/wan2.2-i2v-a14b_high_noise.hmm
[HMM] Loaded component=vae_encode device=1 model=./output/xh2/wan2.2-i2v-a14b_vae_encode.hmm
[HMM] task=i2v-A14B size=(480, 832) frame_num=81 preprocess_device=cpu
Sampling solver=euler, timesteps=[1000, 937, 833, 625], expert_boundary=885.000
[DiT] Activating expert: high_noise_model
[DiT] Step 1/4: timestep=1000.000, expert=high_noise_model, guide_scale=1.000000
[DiT] Step 2/4: timestep=937.000, expert=high_noise_model, guide_scale=1.000000
[DiT] Switching expert: high_noise_model -> low_noise_model; both HMMs remain resident
[DiT] Step 3/4: timestep=833.000, expert=low_noise_model, guide_scale=1.000000
[DiT] Step 4/4: timestep=625.000, expert=low_noise_model, guide_scale=1.000000
Wan2.2 HMM sampling: 100%|█████████████████████████████████████████████████████████| 4/4 [30:05<00:00, 451.41s/it]
Saved video: ./wan2.2_hmm_demo_harvest.mp4 shape=(3, 81, 832, 480)
```

### 4.2 i2v 性能结果

i2v demo 使用 4 个采样 steps。

```bash
Timing
Scope             Count    Total(ms)      Avg(ms)      Min(ms)      Max(ms)  Speed
----------------  -----  -----------  -----------  -----------  -----------  -----
wan2_2                1  1863979.508  1863979.508  1863979.508  1863979.508      -
high_noise_model      3   908976.693   302992.231     6332.850   451439.782      -
  set_input           4    13524.519     3381.130     3331.793     3424.789      -
  infer               4   822081.506   205520.377   205248.556   205804.083      -
  get_output          4     2992.274      748.068      745.752      749.278      -
  load                1     6332.838     6332.838     6332.838     6332.838      -
  postprocess         2        5.783        2.891        2.760        3.023      -
  preprocess          4    63872.335    15968.084    14970.991    16981.065      -
low_noise_model       3   909046.013   303015.338     6068.999   452624.182      -
  set_input           4    13372.293     3343.073     3330.208     3349.343      -
  infer               4   819389.976   204847.494   204302.908   205265.079      -
  get_output          4     2910.864      727.716      723.570      732.097      -
  load                1     6068.985     6068.985     6068.985     6068.985      -
  postprocess         2        5.166        2.583        2.571        2.595      -
  preprocess          4    67114.805    16778.701    14814.125    18823.891      -
t5                    3     2347.334      782.445      187.626     1761.764      -
  set_input           2      215.798      107.899        1.582      214.216      -
  infer               2      356.860      178.430      178.051      178.809      -
  get_output          2        5.913        2.957        2.833        3.080      -
  load                1     1761.735     1761.735     1761.735     1761.735      -
  preprocess          2        6.262        3.131        1.688        4.574      -
vae_decode            2    36490.222    18245.111     2360.987    34129.235      -
  set_input           1      744.521      744.521      744.521      744.521      -
  infer               1    33251.537    33251.537    33251.537    33251.537      -
  get_output          1       93.094       93.094       93.094       93.094      -
  load                1     2360.975     2360.975     2360.975     2360.975      -
  postprocess         1       39.669       39.669       39.669       39.669      -
  preprocess          1        0.228        0.228        0.228        0.228      -
vae_encode            2    25643.400    12821.700     2768.195    22875.205      -
  set_input           1      100.681      100.681      100.681      100.681      -
  infer               1    22037.469    22037.469    22037.469    22037.469      -
  get_output          1      724.559      724.559      724.559      724.559      -
  load                1     2768.183     2768.183     2768.183     2768.183      -
  postprocess         1        0.018        0.018        0.018        0.018      -
  preprocess          1       12.307       12.307       12.307       12.307      -
video_save            1      689.138      689.138      689.138      689.138      -
```

### 4.3 t2v 演示结果

```bash
[HMM] Component device mapping:
  t5: device 0
  vae_decode: device 1
  low_noise_model: device 1
  high_noise_model: device 0
[HMM] Loaded component=t5 device=0 model=./output/xh2/wan2.2-t2v-a14b_t5.hmm
[HMM] Loaded component=vae_decode device=1 model=./output/xh2/wan2.2-t2v-a14b_vae_decode.hmm
[HMM] Loaded component=low_noise_model device=1 model=./output/xh2/wan2.2-t2v-a14b_low_noise.hmm
[HMM] Loaded component=high_noise_model device=0 model=./output/xh2/wan2.2-t2v-a14b_high_noise.hmm
[HMM] task=t2v-A14B size=(480, 832) frame_num=81 preprocess_device=cpu
Sampling solver=euler, timesteps=[1000, 937, 833, 625], expert_boundary=885.000
[DiT] Activating expert: high_noise_model
[DiT] Step 1/4: timestep=1000.000, expert=high_noise_model, guide_scale=1.000000
[DiT] Step 2/4: timestep=937.000, expert=high_noise_model, guide_scale=1.000000
[DiT] Switching expert: high_noise_model -> low_noise_model; both HMMs remain resident
[DiT] Step 3/4: timestep=833.000, expert=low_noise_model, guide_scale=1.000000
[DiT] Step 4/4: timestep=625.000, expert=low_noise_model, guide_scale=1.000000
Wan2.2 HMM sampling: 100%|█████████████████████████████████████████████████████████| 4/4 [30:13<00:00, 453.30s/it]
Saved video: ./wan2.2_hmm_demo_t2v_jellyfish.mp4 shape=(3, 81, 832, 480)
```

### 4.4 t2v 性能结果

t2v demo 使用 4 个采样 steps。

```bash
# 待补充
```

### 4.5 性能指标说明

当前 `demo.py` 使用 `PerfTracker` 记录性能，统计树的根节点为 `wan2_2`。根节点覆盖实际推理和视频保存过程，不包含参数解析、HMM 初始化前的路径处理、`release()` 和进程退出清理。

当前 scope 口径如下：

- `wan2_2.<component>.load`: 对应 HMM 加载时间；
- `wan2_2.<component>.preprocess`: 对应组件输入的 shape、dtype、device、contiguous 和 host-side frontend 处理；
- `wan2_2.<component>.set_input`: 将输入绑定到 HMM 的时间；
- `wan2_2.<component>.infer`: HMM `run()` 和 `sync()` 时间；
- `wan2_2.<component>.get_output`: 从设备读取输出并转为 host Tensor 的时间；
- `wan2_2.<component>.postprocess`: 组件输出转换、CFG 合并和 scheduler latent 更新等后处理；
- `wan2_2`: 根 scope，覆盖推理和视频保存期间未归属到具体模型的 host-side 时间；
- `wan2_2.video_save`: 视频编码和保存时间。

High/low Noise DiT 每个采样 step 会执行 conditional 和 unconditional 两次 forward，因此其 `preprocess`、`set_input`、`infer`、`get_output` 的 `Count` 是采样步数的两倍；CFG 和 scheduler 每个 step 只执行一次，计入当前 expert 的 `postprocess`。这样可以分别观察 high-noise 和 low-noise Expert 的真实计算开销。

当前未单独展示的内容包括 scheduler 初始化、expert 路由判断、timestep reshape、进度条输出以及少量 Python 控制逻辑；这些操作耗时很小，会直接包含在根节点 `wan2_2` 中。

当前已有实测结果（480×832、81 帧、4 steps）中的核心指标为：

- I2V 端到端 `wan2_2`: 约 `1863.980 s`；
- I2V high-noise Expert infer: 约 `822.082 s`；
- I2V low-noise Expert infer: 约 `819.390 s`；
- I2V VAE Encode infer: 约 `22.037 s`；
- I2V VAE Decode infer: 约 `33.252 s`；

以上数据来自当前目录中的历史实测日志，具体耗时会受 HMM 版本、设备分配、Tensor 统计/保存开关和系统负载影响，不应作为所有环境的固定基线。

## 5 免责声明

您明确了解并同意，以下链接中的软件、数据或者模型由第三方提供并负责维护。在以下链接中出现的任何第三方的名称、商标、标识、产品或服务并不构成明示或暗示与该第三方或其软件、数据或模型的相关背书、担保或推荐行为。您进一步了解并同意，使用任何第三方软件、数据或者模型，包括您提供的任何信息或个人数据（不论是有意或无意地），应受相关使用条款、许可协议、隐私政策或其他此类协议的约束。因此，使用链接中的软件、数据或者模型可能导致的所有风险将由您自行承担。
