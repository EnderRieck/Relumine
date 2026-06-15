# ocrforge-web · FastAPI 后端

CultureCourse 演示用 Web 后端：

| 路径 | 用途 |
|------|------|
| `POST /api/convert` | 繁简通译 + 多对一字检测（OpenCC） |
| `POST /api/ocr` | 上传图片 → OCR 识别文本 |
| `GET  /api/evolution` | 字形演化数据库 |
| `GET  /api/evolution/{char}` | 单字详情 |
| `POST /api/culture/analyze` | DeepSeek 古籍实体与关系抽取 |
| `GET  /api/culture/analyses` | 已保存的史脉分析 |
| `PATCH /api/culture/analyses/{id}/review` | 人工确认或驳回实体/关系 |
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
| `OCRFORGE_WEB_LLM_API_KEY` | _(unset)_ | DeepSeek API Key |
| `OCRFORGE_WEB_LLM_BASE_URL` | `https://api.deepseek.com` | DeepSeek 兼容接口地址 |
| `OCRFORGE_WEB_LLM_MODEL` | `deepseek-v4-flash` | 史脉抽取模型 |
| `OCRFORGE_WEB_LLM_TIMEOUT` | `120` | 大模型请求超时，单位秒 |
| `OCRFORGE_WEB_CULTURE_DB_PATH` | `data/culture_graph.sqlite` | 史脉审校数据库 |
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
