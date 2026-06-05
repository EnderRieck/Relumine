# 古籍重光 · Relumine

> 让沉睡在古籍里的繁体汉字重见光明 —— 从识别，到溯源，到文化计算。
>
> *Bringing the characters of ancient texts back to light — from recognition, to provenance, to cultural computing.*

**古籍重光（Relumine）** 是北京邮电大学（BUPT）提出的一项面向汉字文化遗产的计算研究项目。
我们不止于把古籍页面"读"成文字，而是要为每一个繁体字建立**可追溯、可计算、可对齐**的数字身份：
它从何而来、如何一步步简化为今天的字形、在语义空间里又与简体字处于怎样的位置。

OCR 只是入口。最终目标是一套支撑**文化计算（cultural computing）**的基础设施——
让古籍文本不仅能被检索，更能被分析、被度量、被理解。

## 三大支柱

### 1. 古籍 OCR —— 让文字重新可读
面向 DeepSeek-OCR / PaddleOCR-VL 的训练与评测一体框架 [`ocrforge`](#工程框架ocrforge)，
主线是整页 OCR，行级 / 字符级能力用于诊断与训练样本构造。这是整个项目的数据入口：
把扫描影像稳定、高质量地转写为带版面结构的文本。

### 2. 繁简映射数据库 —— 记录每个字的简化历程
为常用繁体字建立结构化的**繁→简映射数据库**，不只记录"繁体 X 对应简体 Y"这一对结果，
而是刻画其**简化历程（simplification provenance）**：

- 一对多 / 多对一的合并与分化关系（如 *發 / 髮 → 发*，*乾 / 幹 / 干 → 干*）；
- 简化所依据的方式（草书楷化、古字复用、形声新造、同音替代、偏旁类推……）；
- 历史层次与依据来源（说文、碑帖、近代简化方案、1956 年《汉字简化方案》等节点）。

目标是让"汉字怎么变成今天这样"成为机器可查询、可统计、可验证的结构化知识，而非散落于注解中的经验。

### 3. 语义空间对齐 —— 通往文化计算
将繁体字与简体字**对齐到同一语义空间**，使得跨字形、跨时代的文本可以在统一表示下比较与计算。
在此之上支撑一系列文化计算任务：古今语义漂移分析、异体字归一、跨时代文本检索、
字形—语义关系建模等。这是把"识别出的文字"升维为"可被研究的文化数据"的关键一步。

```text
扫描影像 ──[① OCR]──▶ 结构化文本 ──[② 繁简映射]──▶ 字级溯源知识 ──[③ 语义对齐]──▶ 文化计算
```

---

## 线上产品 · Live Demo

三大支柱已落地为一个可演示的 Web 产品「**古籍重光**」，对外公开的三个功能恰好对应三条主线：

| Tab | 功能 | 对应支柱 | 做什么 |
|-----|------|----------|--------|
| 壹 · **繁简通译** | 繁⇄简转换 + 合并冲突检测 | ② 繁简映射 | 在 OpenCC 转换基础上，自动标出"多对一"的简化合并点——如 `后 ← 後/后`、`发 ← 發/髮`、`干 ← 乾/幹/干`，把简化造成的语义歧义显式暴露出来 |
| 貳 · **古籍识读** | 古籍影像 OCR | ① OCR | 上传刻本/写本影像，调用**以古籍微调的 PaddleOCR-VL** 模型转写为文本，返回字数与推理延迟；单卡串行队列、可查看排队深度 |
| 參 · **形声流变** | 单字繁简演化时间轴 | ② 繁简映射 | 按 `甲骨→金文→小篆→隶书→楷书(繁)→一简(1956)` 展示典型字的字形流变、合并关系与考据注记，是繁简映射数据库的可视化窗口 |

产品定位一句话（取自首页）：

> 完善现有繁体字典，给出北邮方案 · 以古籍为本微调 PaddleOCR，让刻本重现 · 追溯典型汉字繁简演化

### 系统架构

```text
浏览器 ──▶ Next.js 前端 (:3000) ──/api/* rewrites──▶ FastAPI 后端 (:7860) ──▶ PaddleOCR-VL (常驻 GPU)
                  │                                         │
            cloudflared 隧道                          OpenCC 繁简词典 + evolution.json
            (临时公网 URL)
```

- **前端** `apps/web/`：Next.js 16，中式版式 UI，`next.config.ts` 把 `/api/*` 代理到后端，浏览器只见单一域名。
- **后端** `apps/api/ocrforge_web/`：FastAPI，三个路由 `convert` / `ocr` / `evolution`，OCR 模型在 lifespan 中常驻加载。
- **演化数据** `apps/api/ocrforge_web/data/evolution.json`：当前为 JSON 后端（`JsonEvolutionRepo`，热重载），预留 `SqliteEvolutionRepo` 以便扩展到上百字规模。
- 启动与运维详见 [`apps/RUN.md`](apps/RUN.md)（三服务 tmux 启动手册）。

### API 速览

```text
GET  /api/healthz            # 健康检查 + 模型是否就绪
POST /api/convert            # 繁简转换，返回 result + 合并冲突 collisions
GET  /api/ocr/queue          # 当前 OCR 队列深度
POST /api/ocr                # 上传图片，返回 OCR 文本 / 字数 / 延迟
GET  /api/evolution          # 列出已收录的演化字
GET  /api/evolution/{char}   # 单字完整演化记录（stages / merges / notes）
```

---

## 数据集 · Datasets

项目使用三个公开的历史文献 OCR 数据集。`datasets/` 在本仓库中是指向外部存储的软链接、
**不随仓库分发**（已在 `.gitignore` 中排除），需自行下载并按下述结构放置。

| 数据集 | 内容 | 获取方式 |
|--------|------|----------|
| **TKH**（Tripitaka Koreana in Han） | 高丽大藏经刻本，字符级标注 | HCIILAB 公开发布：<https://github.com/HCIILAB/MTHv2_Datasets_Release> |
| **MTH**（Multiple Tripitaka in Han） | 多版大藏经，字符级标注 | 同上（MTHv2 仓库，含 TKH + MTH） |
| **ICDAR 2019 HDRC-Chinese** | 历史中文文档识别竞赛数据 | ICDAR 2019 Historical Document Reading Competition 官方数据 |

> TKH / MTH 来自 HCIILAB 的 *MTHv2* 数据集；ICDAR2019-HDRC 为竞赛数据，按主办方说明申请/下载。
> 各数据集请遵守其原始许可与引用要求。

### 下载与放置

1. 准备数据根目录（可以是外部大容量盘），并把它软链接到仓库下的 `datasets/`：

   ```bash
   ln -s /path/to/your/datasets $REPO/datasets
   ```

2. 从上述来源下载并解压，按如下结构组织（TKH/MTH 为 Pascal VOC 风格）：

   ```text
   datasets/
     TKH/raw/
       JPEGImages/                 # 页面影像
       Annotations/                # 字符级标注 (xml)
       ImageSets/Main/{train,test}.txt   # 官方划分 id 列表
       Class_label/
     MTH/raw/
       JPEGImages/
       Annotations/
       ImageSets/Main/test.txt     # 官方仅给 test 划分
     ICDAR2019-HDRC-Chinese/
       images/                     # 页面影像
       ground_truth/{segmentation,xml}
   ```

3. 生成训练/测试用的 manifest（`splits/*.jsonl`，记录每张图的相对路径与划分来源）：

   ```bash
   python CultureCourse/tools/prepare_splits.py --dataset all
   # 或单独某个：--dataset tkh | mth | icdar2019
   ```

   - **TKH** 用官方 `train/test.txt` 划分；
   - **MTH** 官方只给 test，脚本按 `seed=20260428` 做 80/20 划分；
   - **ICDAR2019** 无官方划分，同样按固定种子 80/20 划分。

4. 验证数据可被框架正确读取：

   ```bash
   python CultureCourse/tools/check_data.py data=tkh   # 或 data=mth / icdar2019_hdrc / mixed
   ```

数据集路径由 `configs/data/*.yaml` 的 `root` 字段指定（默认即上面的目录结构），`data=mixed` 会合并三者。

---

## 工程框架 `ocrforge`

`ocrforge` 是支柱①的实现：面向 DeepSeek-OCR 的训练 + 测评一体框架，替代旧的临时
`ocr_eval` 脚本体系。主线目标是整页 OCR，行级 / 字符级能力用于诊断和训练样本构造。

### 目录结构

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

### 快速命令

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

### 配置机制

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

### 并行策略

统一字段是 `parallel.mode`：

```text
data      DeepSpeed/DDP 数据并行，当前可执行主路径
model     Accelerate dispatch_model 模块级模型并行
pipeline  Accelerate dispatch_model 分 stage 放置；不是并发 microbatch scheduler
tensor    DeepSpeed init_inference tensor parallel；当前用于评测，不用于训练
```

不兼容的并行模式会明确报错，不会静默退化成单卡。

### 进度条

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

### Checkpoint

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

### 评测粒度

- 页面级：默认主线，整页图输入、整页文本输出、计算页面级 OCR 指标。
- 行级：ICDAR `TextLine` 可用于行级诊断和训练样本构造。
- 字符级：TKH/MTH 字符框可用于单字诊断和训练样本构造，也是繁简映射与字形分析的数据基础。

实验记录保存在 `CultureCourse/EXPERIMENTS.md`。

---

<sub>古籍重光 · Relumine — a Beijing University of Posts and Telecommunications (BUPT) research project on Chinese character heritage computing.</sub>
