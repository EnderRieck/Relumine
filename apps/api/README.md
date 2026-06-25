# ocrforge-web · FastAPI 后端

CultureCourse 演示用 Web 后端：

| 路径 | 用途 |
|------|------|
| `POST /api/convert` | 繁简通译 + 多对一字检测（OpenCC） |
| `POST /api/convert/name` | 人名/地名多源繁→简（CC-CEDICT 词级 + OpenCC/Unihan 字级 + CHISE 佐证）；`/batch` 批量、`/sources` 索引状态 |
| `POST /api/ocr` | 上传图片 → OCR 识别文本（本地 PaddleOCR-VL 还会附逐字置信度与 top-k 候选） |
| `POST /api/ocr/proofread` | 古籍 OCR 校对：按逐字置信度选字，形近字库 + OCR 次优给候选，DeepSeek 仅排序；标注不改字 |
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
# 直连 Brave 不通时可配置代理
OCRFORGE_WEB_BRAVE_PROXY_URL=http://127.0.0.1:7890
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
| `OCRFORGE_WEB_PROOFREAD_CONF_THRESHOLD` | `0.90` | OCR 校对：逐字置信度低于此值的字被选为待校对 |
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
| `OCRFORGE_WEB_BRAVE_PROXY_URL` | _(unset)_ | Brave 搜索代理，直连不通时使用 |
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

## OCR 置信度校对

`services/ocr_proofread.py` 对（OCR 识读出的）古籍文本做校对：标出疑似被识别错的字、给出候选，
但**只标注不改写**——判断权交给专家。接口 `POST /api/ocr/proofread`，助手工具 `proofread_ocr`，
前端在「古籍识读」页点「校对」即可，待校对字按 OCR 把握度分级框标、点击出候选。三者分工明确：

1. **选字 = OCR 逐字置信度（唯一闸门）**：本地 PaddleOCR-VL 贪婪解码时每个 token 的 softmax 概率即模型把握。
   `generate_page_with_confidence` 用 `output_scores + compute_transition_scores` 取概率，再经
   `models/token_confidence.py` 的 `text_anchored_pieces` 做 **token→字对齐**（以最终文本为锚，对 byte-fallback
   稳健）。置信度低于 `settings.proofread_conf_threshold`（默认 0.90）的字被选为「待校对」，取最低的至多 60 个。
2. **候选 = 形近字库 + OCR 次优读法**：选中的字，候选来自全量形近字索引（见下）+ 该字的 OCR top-k 次优 token。
   OCR 次优是强证据（模型自己拿不准的读法），排在形近候选之前。
3. **排序 = DeepSeek（可选，仅排序）**：若配置 `settings.llm_*`，DeepSeek **只对已选中字的候选按上下文重排**——
   不参与选字、不新增候选、不造词。未配置 / 调用失败则保留「OCR 次优 + 形近」原序。

每个待校对字带 `ocr_confidence`（OCR 识别把握）与 `confidence`（= 1 − 置信度，越不确定越高）。
选字依赖逐字置信度，故只在**本地 PaddleOCR-VL** 后端可用；remote / vision 后端或纯文本调用拿不到置信度，
返回空风险 + 说明（不再用语言模型瞎猜选字）。前后端一律按**码点**索引，避免扩展区汉字的 UTF-16 错位。

### 全量形近字索引

`data/confusable_index.v1.json`：每个繁体字 → 最像它的 top-10 形近字（OCR 易混候选），由
`analysis/hanzi_databases/scripts/build_confusable_index.py` 离线构建（依赖 raw CHISE/Unihan，产物随仓库提交）：

- **合体字**用 CHISE IDS 结构相似度（共享部件 + IDS 编辑距离，相似度 ≥0.6、笔画差 ≤2）自动算出；
- **原子字**（`己/已/巳`、`戊/戌/戍`、`土/士`、`未/末`、`日/曰` 等部件法覆盖不到的）用**人工形近组**补齐；
- 只按繁体字形建（古籍 OCR 即繁体）——不做简体投影，因简化常削掉共享部件（如繁体 `慄/憐` 形近，但简体 `栗/怜` 毫不像）。

> 说明：约 3650 字有形近候选（不是每个字都有形近字）。token→字对齐与形近逻辑已离线单测；
> 逐字置信度的真实数值需在能跑 PaddleOCR-VL 的部署环境验证。`proofread_conf_threshold` 可按实测调松紧。

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
