# CultureCourse OCRForge

`ocrforge` 是面向 DeepSeek-OCR 的训练+测评一体框架。它替代旧的临时
`ocr_eval` 脚本体系，主线目标是整页 OCR，行级/字符级能力用于诊断和训练样本构造。

## 目录结构

```text
CultureCourse/
  EXPERIMENTS.md        # 个人实验记录
  configs/              # Hydra/OmegaConf 配置
  tools/                # train/evaluate/check_data 等入口
  src/ocrforge/         # Python 包
  runs/                 # 每次运行的配置快照、日志、指标、预测
```

核心模块：

```text
src/ocrforge/data        数据集读取、统一 OCRSample schema
src/ocrforge/processing  DeepSeek 图像/文本 processor、prompt
src/ocrforge/models      DeepSeek-OCR-2 wrapper、微调策略
src/ocrforge/training    训练循环、checkpoint 预留
src/ocrforge/evaluation  页面级评测、指标、输出 writer
src/ocrforge/parallel    多 GPU 并行配置和兼容检查
src/ocrforge/runtime     运行目录、config 快照、环境记录
```

## 快速命令

DeepSeek-OCR 相关命令必须在 `deepseek-ocr2-maca` 环境里运行：

```bash
conda activate deepseek-ocr2-maca

python CultureCourse/tools/check_data.py data=tkh
python CultureCourse/tools/evaluate.py experiment=full_eval eval.limit=2
python CultureCourse/tools/train.py experiment=deepseek_full_finetune data.limit=2 train.max_steps=1
```

不激活环境时可以用：

```bash
conda run -n deepseek-ocr2-maca python CultureCourse/tools/check_data.py data=tkh
```

PaddleOCR-VL 使用独立环境，避免和 DeepSeek-OCR-2 需要的 transformers 版本冲突：

```bash
python CultureCourse/tools/run.py evaluate --conda-env paddleocr-vl --devices 0 \
  experiment=full_eval model=paddleocr_vl data=tkh data.split=test eval.limit=10
```

模型文件保存在：

```text
CultureCourse/models/PaddleOCR-VL-1.5
```

多卡命令可以用 `run.py` 简化。`--devices` 是唯一的设备入口：它会设置
`CUDA_VISIBLE_DEVICES`，并自动注入进程内逻辑编号的 `parallel.devices`。其中
`parallel=data/tensor` 多卡时会启动 `torchrun`，`parallel=model/pipeline` 多卡时保持单进程多卡。

```bash
python CultureCourse/tools/run.py evaluate --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=full_eval data=tkh data.split=test data.limit=10 eval.limit=10
```

## 配置机制

配置由 `CultureCourse/configs/config.yaml` 组合各配置组：

```text
model/ data/ train/ eval/ parallel/ runtime/ logging/ experiment/
```

每次运行会写入：

```text
runs/<task>/<timestamp>_<experiment>/
  config_resolved.yaml     # 完整最终配置
  config_overrides.yaml    # 命令行显式覆盖
  env.json                 # 环境、cwd、项目根、配置摘要
  command.txt              # 原始命令
  metrics.json             # 汇总指标
```

默认评测只写 `predictions.jsonl` 和指标文件，不创建逐样本 `samples/` 目录。
需要保存 DeepSeek 的可视化/裁剪结果时显式指定：

```bash
python CultureCourse/tools/run.py evaluate --conda-env deepseek-ocr2-maca --devices 0 \
  experiment=full_eval eval.save_samples=20
```

## 并行策略

统一字段是 `parallel.mode`：

```text
data      DeepSpeed/DDP 数据并行，当前可执行主路径
model     Accelerate dispatch_model 模块级模型并行
pipeline  Accelerate dispatch_model 分 stage 放置；不是并发 microbatch scheduler
tensor    DeepSpeed init_inference tensor parallel；当前用于评测，不用于训练
```

不兼容的并行模式会明确报错，不会静默退化成单卡。

## 进度条

训练和评测默认显示 tqdm 风格进度条。单进程时直接按本进程进度更新；多进程
DDP/torchrun 时只由 rank 0 显示，所有 rank 通过独立的进度通信组定期汇总完成量，
不是按样本写进度文件。

```bash
# 关闭进度条
python CultureCourse/tools/run.py evaluate --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=full_eval logging.progress.enabled=false

# 降低分布式进度刷新频率，减少通信开销
python CultureCourse/tools/run.py train --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=deepseek_full_finetune logging.progress.refresh_seconds=5
```

## Checkpoint

训练里的 `step` 现在是一次 `optimizer.step()`。有效 batch：

```text
global_batch_size = train.batch_size * train.gradient_accumulation_steps * world_size
```

示例：

```bash
python CultureCourse/tools/run.py train --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=deepseek_full_finetune \
  batch_size=2 grad_accum=4 max_step=1000 eval_every_steps=200
```

`run.py` 会把这些短参数映射为：

```text
batch_size -> train.batch_size
grad_accum -> train.gradient_accumulation_steps
max_step/max_steps -> train.max_steps
eval_every_steps -> train.eval_every_steps
```

```bash
python CultureCourse/tools/run.py train \
    --conda-env paddleocr-vl \
    --devices 0,1,2,3,4,5,6,7 \
    experiment=train_paddle \
    train.learning_rate=2e-6 \
    max_step=500 \
    train.eval_every_steps=50 \
    train.save_every_steps=50 \
    experiment.name=paddle_v1_lr2e-6

```

训练中周期评测写到：

```text
runs/train/<run_name>/eval/step_000200/
  metrics.json
  predictions.jsonl
```

训练默认保存到本次运行目录下：

```text
runs/train/<run_name>/
  checkpoints/
    step_000500/   # train.save_every_steps 控制，设为 0 可关闭周期保存
    final/         # train.save_final 控制
    trainer_state.pt
```

后续评测指定新模型：

```bash
python CultureCourse/tools/run.py evaluate --conda-env deepseek-ocr2-maca --devices 0 \
  experiment=full_eval model.path=CultureCourse/runs/train/<run_name>/checkpoints/final
```

继续训练时同时指定模型权重和 trainer state：

```bash
python CultureCourse/tools/run.py train --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=deepseek_full_finetune \
  model.path=CultureCourse/runs/train/<run_name>/checkpoints/step_000500 \
  train.resume_from_checkpoint=CultureCourse/runs/train/<run_name>/checkpoints/step_000500 \
  max_step=1000
```

训练结束后默认生成 loss 曲线：

```text
runs/train/<run_name>/loss_curve.png
runs/train/<run_name>/loss_curve.csv
```

给历史 run 补画：

```bash
conda run --no-capture-output -n deepseek-ocr2-maca python CultureCourse/tools/plot_train.py \
  CultureCourse/runs/train/<run_name>
```

示例：

```bash
# 4 卡 DDP 训练
python CultureCourse/tools/run.py train --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=deepseek_full_finetune

# 4 卡 DDP 测评
python CultureCourse/tools/run.py evaluate --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=deepseek_full_finetune

# 模块级模型并行训练
python CultureCourse/tools/run.py train --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=deepseek_full_finetune data=tkh data.limit=1 train.max_steps=1 \
  parallel=model

# 分 stage 放置的 pipeline 模式
python CultureCourse/tools/run.py evaluate --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=full_eval data=tkh data.split=test data.limit=1 eval.limit=1 \
  parallel=pipeline parallel.stages=2 parallel.partition.lm_head_stage=1

# DeepSpeed tensor parallel 评测
python CultureCourse/tools/run.py evaluate --conda-env deepseek-ocr2-maca --devices 0,1 \
  experiment=full_eval data=tkh data.split=test data.limit=2 eval.limit=2 \
  parallel=tensor parallel.tensor_parallel_size=2
```

## 评测粒度

- 页面级：默认主线，整页图输入、整页文本输出、计算页面级 OCR 指标。
- 行级：ICDAR `TextLine` 可用于行级诊断和训练样本构造。
- 字符级：TKH/MTH 字符框可用于单字诊断和训练样本构造。

实验记录保存在 `CultureCourse/EXPERIMENTS.md`。
