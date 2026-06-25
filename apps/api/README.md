# ocrforge-web · FastAPI 后端

CultureCourse 演示用 Web 后端：

| 路径 | 用途 |
|------|------|
| `POST /api/convert` | 繁简通译 + 多对一字检测（OpenCC） |
| `POST /api/convert/name` | 人名/地名多源繁→简（CC-CEDICT 词级 + OpenCC/Unihan 字级 + CHISE 佐证）；`/batch` 批量、`/sources` 索引状态 |
| `POST /api/ocr` | 上传图片 → OCR 识别文本（本地 PaddleOCR-VL 还会附逐字置信度与 top-k 候选） |
| `POST /api/ocr/proofread` | 古籍 OCR 文本校对：OCR 逐字置信度 + 部件形近字 + DeepSeek 上下文，标注可疑字 + 给候选，不改原文 |
| `GET  /api/evolution` | 字形演化数据库 |
| `GET  /api/evolution/{char}` | 单字详情 |
| `POST /api/culture/analyze` | DeepSeek 古籍实体与关系抽取 |
| `GET  /api/culture/analyses` | 已保存的史脉分析 |
| `PATCH /api/culture/analyses/{id}/review` | 人工确认或驳回实体/关系 |
| `POST /api/agent/chat` | 智能助手对话（SSE 流式，复用 DeepSeek，支持工具调用） |
| `POST /api/agent/continue` | 客户端工具执行结果回传、续跑对话 |
| `GET  /api/agent/health` | 助手各能力（DeepSeek / Brave / 浏览器 / 技能）就绪状态 |
| `GET  /api/agent/skills` | 列出可用技能 |
| `GET  /api/healthz` | 服务健康 + 模型加载状态 |

## 启动

```bash
OCRFORGE_WEB_OCR_BACKEND=auto conda run -n base uvicorn ocrforge_web.main:app \
  --host 127.0.0.1 --port 7860 \
  --app-dir apps/api
```

`OCRFORGE_WEB_OCR_BACKEND=auto` 会优先尝试 PaddleOCR-VL；如果本机没有 checkpoint 或深度学习依赖，则自动回退到 macOS Vision OCR。当前本机使用的是 macOS Vision OCR，`/api/healthz` 的 `model_loaded` 为 `true` 时即可上传图片识别。

如果 OCR 由队友或云服务器运行，本机只作为前端和数据库服务：

```bash
OCRFORGE_WEB_REMOTE_OCR_URL=http://队友服务器:端口/api/ocr \
OCRFORGE_WEB_OCR_BACKEND=remote \
conda run -n base uvicorn ocrforge_web.main:app \
  --host 127.0.0.1 --port 7860 \
  --app-dir apps/api
```

远程接口需要兼容当前格式：接收 `multipart/form-data` 的 `file` 字段，返回 JSON，例如 `{"text": "识别结果"}`。

### DeepSeek 史脉分析

复制示例配置并填入自己的 Key，`.env` 已被 Git 忽略：

```bash
cp apps/api/.env.example apps/api/.env
```

史脉分析使用 JSON 输出模式，从古籍原文中抽取实体和关系。结果写入本地
`ocrforge_web/data/culture_graph.sqlite`，并保存原文证据、置信度与人工审校状态。

### Agent 智能助手（侧边栏）

复用同一套 DeepSeek 配置（`OCRFORGE_WEB_LLM_*`）。前端右侧"智能助手"侧边栏调用
`POST /api/agent/chat`（SSE 流式）。Agent Harness（`ocrforge_web/agent/`）管理上下文、
工具与技能：

- **服务端工具**：`search_characters` / `get_character_detail` / `get_database_stats` /
  `get_cl_analysis` / `convert_text` / `convert_name` / `proofread_ocr` /
  `list_culture_analyses` / `get_culture_analysis`
  （复用现有只读仓储与 OpenCC）、`web_search`（Brave）、`browse_page`（Playwright 无头）。
- **客户端工具**：`get_page_context` 读取页面快照；`switch_tab` / `set_convert_input` /
  `run_convert` / `set_evolution_search` / `select_character` / `set_culture_text` /
  `run_culture_analysis` 直接操作前端界面（经 SSE `client_tool_call` 事件 → 前端执行 →
  `/api/agent/continue` 回填续跑）。
- **技能**：`ocrforge_web/agent/skills/builtin/*/SKILL.md`（带 frontmatter），通过
  `list_skills` / `run_skill` 渐进披露。内置 `char-deep-dive`、`web-lookup`。

可选能力的额外配置：

```bash
# 联网搜索（Brave Search API）
OCRFORGE_WEB_BRAVE_API_KEY=...
# 无头浏览器（默认开启），首次需安装内核：
pixi run playwright install chromium
# 默认模型若不支持 function-calling，可切换：
OCRFORGE_WEB_AGENT_MODEL=deepseek-chat
```

会话保存在进程内存中（重启即失），不落库。

## 配置

环境变量前缀 `OCRFORGE_WEB_`，详见 `settings.py`：

| 变量 | 默认 | 说明 |
|------|------|------|
| `OCRFORGE_WEB_PADDLE_CKPT` | `runs/train/.../step_000200` | 模型 checkpoint 目录 |
| `OCRFORGE_WEB_PADDLE_DTYPE` | `bfloat16` | 推理精度 |
| `OCRFORGE_WEB_PADDLE_DEVICE` | `cuda:0` | GPU 设备 |
| `OCRFORGE_WEB_PADDLE_ATTN` | `flash_attention_2` | 注意力实现（无 flash 时改 `sdpa`） |
| `OCRFORGE_WEB_OCR_BACKEND` | `auto` | `auto` / `paddle` / `vision` |
| `OCRFORGE_WEB_REMOTE_OCR_URL` | _(unset)_ | 队友/云服务器 OCR 接口地址，设置后可转发图片 |
| `OCRFORGE_WEB_REMOTE_OCR_TIMEOUT` | `120` | 远程 OCR 请求超时时间，单位秒 |
| `OCRFORGE_WEB_EVOLUTION_BACKEND` | `sqlite` | `json` / `sqlite` |
| `OCRFORGE_WEB_EVOLUTION_PATH` | `data/relumine_char_db.v2.sqlite` | 演化数据文件 |
| `OCRFORGE_WEB_HANZI_CONVERT_PATH` | `data/hanzi_convert.sqlite` | 多源繁→简转换索引（缺失则退化为纯 OpenCC 字级） |
| `OCRFORGE_WEB_LLM_API_KEY` | _(unset)_ | DeepSeek API Key |
| `OCRFORGE_WEB_LLM_BASE_URL` | `https://api.deepseek.com` | DeepSeek 兼容接口地址 |
| `OCRFORGE_WEB_LLM_MODEL` | `deepseek-v4-flash` | 史脉抽取模型 |
| `OCRFORGE_WEB_LLM_TIMEOUT` | `120` | 大模型请求超时，单位秒 |
| `OCRFORGE_WEB_CULTURE_DB_PATH` | `data/culture_graph.sqlite` | 史脉审校数据库 |
| `OCRFORGE_WEB_CBDB_PATH` | `data/authority/cbdb/cbdb.sqlite3` | CBDB 本地 SQLite |
| `OCRFORGE_WEB_CHGIS_API_URL` | `https://chgis.hudci.org/tgaz/placename` | CHGIS Temporal Gazetteer API |
| `OCRFORGE_WEB_AUTHORITY_TIMEOUT` | `15` | 权威库请求超时，单位秒 |

## CBDB / CHGIS 权威对齐

下载并校验最新版 CBDB：

```bash
python analysis/authority_databases/download_cbdb.py
```

人物实体会与 CBDB 的规范姓名、异名、生卒年和索引年对齐。地点实体通过
CHGIS 官方只读 Temporal Gazetteer API 检索，保存历史有效年代、类型、上级政区、
经纬度与来源链接。CHGIS 原始数据禁止再分发，因此项目不会提交其数据包。

人物匹配做了去噪：被多人共享的字/号（如 `子楚`）等**歧义异名**会被弃用、**精确名优先于异名**、
异名匹配按本篇年代过滤掉**跨代重名**，并且不再用匹配结果覆写 `normalized_name`，使重新对齐
（`POST /api/culture/analyses/{id}/link-authorities`）保持幂等。对齐到的（繁体）规范名还会经下文
的多源转换实时给出简体形（`canonical_name_simplified`）与各库证据。
| `OCRFORGE_WEB_AGENT_MODEL` | _(unset)_ | 助手模型，缺省回退 `LLM_MODEL` |
| `OCRFORGE_WEB_BRAVE_API_KEY` | _(unset)_ | Brave 搜索 Key，启用 `web_search` |
| `OCRFORGE_WEB_AGENT_ENABLE_BROWSER` | `true` | 是否启用 Playwright 无头浏览器工具 |
| `OCRFORGE_WEB_AGENT_MAX_STEPS` | `12` | 单轮对话最多工具调用步数 |
| `OCRFORGE_WEB_AGENT_SESSION_TTL` | `3600` | 内存会话存活秒数 |
| `OCRFORGE_WEB_OCR_WARMUP` | `true` | 启动时是否跑一次 1×1 warm-up |
| `OCRFORGE_WEB_SKIP_OCR` | _(unset)_ | 设为 `1` 可跳过模型加载（用于纯前端联调） |

## 模型不可用时启动

需要先跑 `/api/convert` 与 `/api/evolution` 但暂不加载模型：

```bash
OCRFORGE_WEB_SKIP_OCR=1 conda run -n base uvicorn ocrforge_web.main:app ...
```

`/api/ocr` 此时返回 503。

## 代码复用

- `services/ocr_service.py` 在有 PaddleOCR-VL checkpoint 时调用
  `ocrforge.models.factory.build_model_module` 与 `PaddleOCRVLModule.apply_parallel` /
  `generate_page`；没有 checkpoint 时使用 macOS Vision OCR 后备链路。
- `ocrforge_web/__init__.py` 在导入时把 `CultureCourse/src` 加入 `sys.path`，
  与 `tools/_bootstrap.py` 同思路。

## OCR 上下文校对

`services/ocr_proofread.py` 对（OCR 识读出的）古籍文本做**上下文校对**：找出疑似被识别错的字、
给出候选，但**只标注不改写**——判断权交给专家。接口 `POST /api/ocr/proofread`（DeepSeek 未配置返回
503），助手工具 `proofread_ocr`，前端在「古籍识读」页点「校对」即可，风险字按把握度分级框标、点击出候选。

判定不靠单一信号，三层叠加：

1. **OCR 逐字置信度（主闸门）**：本地 PaddleOCR-VL 贪婪解码时，每个 token 的 softmax 概率即模型把握。
   `generate_page_with_confidence` 用 `return_dict_in_generate + output_scores` 取分数、
   `compute_transition_scores` 还原逐 token 概率，再经 `models/token_confidence.py` 做 **token→字对齐**
   （增量 decode 求每 token 新增片段、跨多 token 的字取最小概率、单 token 单字位附 top-k 次优读法当候选）。
   低置信字优先送校对、并把 OCR 自己的 top-k 候选并入；非前缀稳定或任一步出错时**优雅退回纯文本**，不拖累识读。
2. **形近字先验**：从 `cl_analysis.v1.json` 的 `ocr_confusion.top_pairs`（CHISE 部件结构在繁体字形上算的
   形近字对）建「字→易混字」索引，作候选先验喂给模型，并把模型漏掉的形近孪生字强制补进候选；
3. **上下文判定**：DeepSeek（复用 `settings.llm_*`）结合文义、搭配、人名地名书名判断某字是否可疑、该改成什么；
   并被告知「OCR 低置信位」清单优先核查。OCR 硬低置信（< 0.6）但模型未标的位置，单独兜底成「低置信」风险交专家过目。

每个风险字带两个独立信号：`confidence`（语言模型判定的误识把握）与 `ocr_confidence`（OCR 模型识别置信度）。
置信度只在本地 PaddleOCR-VL 后端有；remote / vision 后端拿不到，退化为「形近 + 上下文」两层，行为不变。

**位置对齐**不让模型数下标（模型对字符计数不可靠）：模型只回包含可疑字的**原文片段 `snippet`**，后端用
`text.find(snippet)+片段内偏移` 算出绝对码点下标，并核验 `text[pos]==suspect`，定位不上的直接丢弃。
前后端一律按**码点**（Python `str` / JS `Array.from`）索引，避免扩展区汉字的 UTF-16 错位。

> 说明：`top_pairs` 是从 8 万余对里截断的高相似子集（约覆盖百余字），形近表只作候选先验，真正判断靠
> 置信度 + 上下文，覆盖不全不影响可用。后续增强：从全量 CHISE 建部件倒排进一步扩大形近覆盖。
> token→字对齐逻辑（`token_confidence.py`）已离线单测；逐字置信度的真实数值需在能跑 PaddleOCR-VL 的部署环境验证。

## 多源繁→简转换

`services/name_convert.py` 把繁体专名（人名/地名，尤其 CBDB/CHGIS 权威名）转成简体，
联合项目的四个文字数据库，而非只靠 OpenCC 逐字：

1. **词级优先**：整名用 CC-CEDICT 词条贪婪最长匹配（`錢鍾書 → 钱钟书`，胜过逐字的 `钱锺书`）；
2. **字级兜底**：词典未收的字用 OpenCC 转换，并与 Unihan `kSimplifiedVariant` 交叉校验；
3. **结构佐证**：附 CHISE IDS 部件分解辅助辨别形近变体；
4. 每段返回**置信度**、**分歧标注**（不同库给出不同简体时列出候选）与各库证据。

接口 `POST /api/convert/name`（含 `/batch` 批量、`/sources` 索引状态），助手工具 `convert_name`，
并在 `authority_linker` 中为每个权威匹配挂上 `canonical_name_simplified` 与转换明细。

运行时索引 `data/hanzi_convert.sqlite`（CC-CEDICT 词对 / Unihan 变体 / CHISE IDS）由离线脚本构建、
随仓库提交；原始 dump 放在 `analysis/hanzi_databases/raw/`（忽略提交）。重建：

```bash
pixi run python analysis/hanzi_databases/scripts/build_convert_index.py
```

索引缺失时服务自动退化为纯 OpenCC 字级转换（置信度更低、无证据）。

> 前端代理目标支持用环境变量 `API_PROXY_TARGET` 覆盖（默认 `http://127.0.0.1:7860`），
> 便于在 7860 被占用时把后端跑到其他端口；见 `apps/web/src/app/api/[...path]/route.ts`。
