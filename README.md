<p align="center">
  <img src="assets/logo_banner.png" alt="古籍重光 Logo" width="360" />
</p>

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

三大支柱已落地为一个可演示的 Web 产品「**古籍重光**」，并在其上增加可审校的文化关系计算：

| Tab | 功能 | 对应支柱 | 做什么 |
|-----|------|----------|--------|
| 壹 · **繁简通译** | 繁⇄简转换 + 合并冲突检测 | ② 繁简映射 | 在 OpenCC 转换基础上，自动标出"多对一"的简化合并点——如 `后 ← 後/后`、`发 ← 發/髮`、`干 ← 乾/幹/干`，把简化造成的语义歧义显式暴露出来 |
| 貳 · **古籍识读** | 古籍影像 OCR + 置信度校对 | ① OCR | 上传刻本/写本影像，调用**以古籍微调的 PaddleOCR-VL** 模型转写为文本，返回字数与推理延迟；单卡串行队列、可查看排队深度。识读后可一键**校对**：按 OCR 逐字置信度选出待校对字、用全量形近字库 + OCR 次优给候选（DeepSeek 可选排序），按把握度分级框标，**只建议不改字**，关键存疑交专家定夺 |
| 參 · **形声流变** | 单字繁简演化时间轴 | ② 繁简映射 | 按 `甲骨→金文→小篆→隶书→楷书(繁)→一简(1956)` 展示典型字的字形流变、合并关系与考据注记，是繁简映射数据库的可视化窗口 |
| 肆 · **史脉** | 古籍实体关系图谱 | ③ 语义对齐 | 调用 DeepSeek 抽取人物、地点、官职、时间和事件，再以 CBDB 校验人物、CHGIS 对齐历史地名与坐标；权威库的**繁体**规范名经多源校验**实时繁→简**显示（繁体作辅注 + 各库证据）；生成今译、关系图、空间分布和时间线，并保留原文证据与人工审校状态 |

产品定位一句话（取自首页）：

> 完善现有繁体字典，给出北邮方案 · 以古籍为本微调 PaddleOCR，让刻本重现 · 追溯典型汉字繁简演化

### 系统架构

```text
浏览器 ──▶ Next.js 前端 (:3000) ──/api/* proxy──▶ FastAPI 后端 (:7860)
                  │                                  ├──▶ PaddleOCR / 远程 OCR
            cloudflared 隧道                         ├──▶ OpenCC + 汉字 SQLite
            (临时公网 URL)                           └──▶ DeepSeek + 关系 SQLite
```

- **前端** `apps/web/`：Next.js 16，中式版式 UI，App Router 代理 `/api/*` 到后端，支持 OCR 长请求与 DeepSeek 长请求。
- **后端** `apps/api/ocrforge_web/`：FastAPI，包含 `convert` / `ocr` / `evolution` / `culture` 四组路由。
- **汉字数据** `apps/api/ocrforge_web/data/relumine_char_db.v2.sqlite`：4,941 字繁简映射与文化计算字段。
- **史脉数据** `culture_graph.sqlite`：本地生成并忽略提交，按文献保存实体、关系、证据和人工审校状态。
- 启动与运维详见 [`apps/RUN.md`](apps/RUN.md)（三服务 tmux 启动手册）。

### API 速览

```text
GET  /api/healthz            # 健康检查 + 模型是否就绪
POST /api/convert            # 繁简转换，返回 result + 合并冲突 collisions
POST /api/convert/name       # 人名/地名多源繁→简（CC-CEDICT 词级 + OpenCC/Unihan 字级 + CHISE 佐证）
GET  /api/ocr/queue          # 当前 OCR 队列深度
POST /api/ocr                # 上传图片，返回 OCR 文本 / 字数 / 延迟
POST /api/ocr/proofread      # OCR 置信度校对：按逐字置信度选字 + 形近字/OCR候选（不改原文）
GET  /api/evolution          # 列出已收录的演化字
GET  /api/evolution/{char}   # 单字完整演化记录（stages / merges / notes）
GET  /api/culture/status     # DeepSeek 是否已配置
POST /api/culture/analyze    # 古籍实体、关系、今译和时间线
POST /api/culture/analyses/{id}/link-authorities # CBDB/CHGIS 重新对齐
PATCH /api/culture/analyses/{id}/review  # 确认或驳回抽取结果
POST /api/agent/chat         # 智能助手对话（SSE 流式，复用 DeepSeek，支持工具调用）
POST /api/agent/continue     # 客户端工具执行结果回传、续跑对话
GET  /api/agent/health       # 助手各能力（DeepSeek / Brave / 浏览器 / 技能）状态
GET  /api/agent/skills       # 列出可用技能
```

> 右侧"智能助手"侧边栏复用同一套 DeepSeek 配置，可读写页面、查字库、联网搜索、看网页、跑技能。详见 [`apps/api/README.md`](apps/api/README.md#agent-智能助手侧边栏)。

### OCR 置信度校对（待校对字框标注 + 候选建议）

OCR 把"图"变成"文"，但形近误识难免。识读页的「校对」按钮对识读文本做一遍校对，
定位为**辅助专家、而非自动改字**——把字框出来、给候选，判断权交给人。三者各管一摊：

- **选字 = OCR 逐字置信度**：本地 PaddleOCR-VL 解码时每个字的把握（softmax 概率）经 token→字对齐取出，
  把握低于阈值（默认 0.90）的字即「待校对」。选字**只看 OCR 自己有没有把握**，不靠语言模型瞎猜。
- **候选 = 形近字库 + OCR 次优**：选中的字，候选来自[全量形近字索引](#全量形近字索引-ocr-易混候选)（每字 top-10）
  + 该字的 OCR top-k 次优读法（强证据，排前面）。
- **排序 = DeepSeek（可选）**：若配置，DeepSeek **只对已选中字的候选按上下文重排**，不选字、不造词；
  没配置就保留"OCR 次优 + 形近"原序。

每个待校对字带 `ocr_confidence`（OCR 识别把握）；按把握分级框标，点击弹出候选，专家采纳某候选才在本地替换、
或"保留原字"。识读页还有「OCR 置信度」开关，把整段按逐字把握上色（越红越没把握）。前后端一律按码点对齐，避免错位。

接口 `POST /api/ocr/proofread`、助手工具 `proofread_ocr`。选字依赖逐字置信度，故只在本地 PaddleOCR-VL 后端可用；
remote / vision 后端拿不到置信度，返回空结果 + 说明。

#### 全量形近字索引（OCR 易混候选）

`data/confusable_index.v1.json`：每个繁体字 → 最像它的 top-10 形近字，离线由
`build_confusable_index.py` 构建。**合体字**用 CHISE IDS 部件结构相似度自动算（相似度≥0.6、笔画差≤2），
**原子字**（己/已/巳、戊/戌/戍、土/士、未/末 这类部件法盖不到的）用人工形近组补齐；只按繁体字形建
（古籍 OCR 即繁体），不做简体投影（简化常削掉共享部件，繁体形近的字简体未必形近）。约 3650 字有候选。

### 多源繁简转换（权威名实时繁→简）

CBDB / CHGIS 等权威库以**繁体**存储规范名。史脉对齐到权威名后，会用一套**多源繁→简转换**把它实时转为简体显示，尤其适合人名、地名这类专名——它联合项目的四个文字数据库，而非只靠 OpenCC 逐字：

- **词级优先**：整名先查 CC-CEDICT 词条（如 `錢鍾書 → 钱钟书`，胜过逐字 OpenCC 的 `钱锺书`）；
- **字级兜底**：词典未收的字用 OpenCC 转换，并与 Unihan `kSimplifiedVariant` 交叉校验；
- **结构佐证**：附 CHISE IDS 部件分解，辅助辨别形近变体；
- 每段给出**置信度**与**分歧标注**：不同库给出不同简体时显式提示并列出候选。

运行时索引 `apps/api/ocrforge_web/data/hanzi_convert.sqlite` 由 `analysis/hanzi_databases/scripts/build_convert_index.py` 离线从 Unihan / CC-CEDICT / CHISE IDS 提炼而成（原始 dump 保持忽略提交）。同时提供独立接口 `POST /api/convert/name`（含 `/batch`、`/sources`）与助手工具 `convert_name`。

> 配套加固了 CBDB 人物匹配：弃用被多人共享的字/号（如 `子楚`）等歧义异名、精确名优先于异名、按本篇年代过滤跨代重名，并使重新对齐保持幂等。

### 本地启动（Windows + pixi）

需要**两个终端**，各跑一个、保持不关。前端会把 `/api/*` 自动代理到后端（`apps/web/src/app/api/[...path]/route.ts`），所以浏览器只需访问一个地址。

```bash
# 终端 1 · 后端 API（端口 7860）
cd apps/api
pixi run python -m uvicorn ocrforge_web.main:app --host 127.0.0.1 --port 7860
#   改了后端代码想自动重载：在末尾加 --reload

# 终端 2 · 前端 Web（端口 3000）
cd apps/web
npm install        # 仅首次：安装依赖
npm run dev
```

启动后打开 **http://localhost:3000**。

- **配置 Key**：`cp apps/api/.env.example apps/api/.env`，填入 `OCRFORGE_WEB_LLM_API_KEY`（DeepSeek，史脉与助手共用）；可选 `OCRFORGE_WEB_BRAVE_API_KEY`（助手联网搜索）。改完需**重启后端**才生效。
- **无头浏览器**（助手看网页）首次需装内核：`cd apps/api && pixi run playwright install chromium`。
- **OCR tab** 依赖 PaddleOCR-VL checkpoint；本地无 checkpoint 时该 tab 不可用（`/api/healthz` 的 `model_loaded=false`），其余功能不受影响。
- 公网演示（cloudflared 临时隧道、tmux 多服务）见 [`apps/RUN.md`](apps/RUN.md)。

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
