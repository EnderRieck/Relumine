# ocrforge-web · FastAPI 后端

CultureCourse 演示用 Web 后端，提供三个端点：

| 路径 | 用途 |
|------|------|
| `POST /api/convert` | 繁简通译 + 多对一字检测（OpenCC） |
| `POST /api/ocr` | 上传图片 → PaddleOCR-VL 识别为繁体文本 |
| `GET  /api/evolution` | 字形演化字典（10 字） |
| `GET  /api/evolution/{char}` | 单字详情 |
| `GET  /api/healthz` | 服务健康 + 模型加载状态 |

## 启动

```bash
conda run -n paddleocr-vl uvicorn ocrforge_web.main:app \
  --host 127.0.0.1 --port 7860 \
  --app-dir CultureCourse/apps/api
```

首次加载 PaddleOCR-VL checkpoint 约 15-20s，warm-up 完成后 `/api/healthz` 的 `model_loaded` 转 `true`。

## 配置

环境变量前缀 `OCRFORGE_WEB_`，详见 `settings.py`：

| 变量 | 默认 | 说明 |
|------|------|------|
| `OCRFORGE_WEB_PADDLE_CKPT` | `runs/train/.../step_000200` | 模型 checkpoint 目录 |
| `OCRFORGE_WEB_PADDLE_DTYPE` | `bfloat16` | 推理精度 |
| `OCRFORGE_WEB_PADDLE_DEVICE` | `cuda:0` | GPU 设备 |
| `OCRFORGE_WEB_PADDLE_ATTN` | `flash_attention_2` | 注意力实现（无 flash 时改 `sdpa`） |
| `OCRFORGE_WEB_EVOLUTION_BACKEND` | `json` | `json` / `sqlite`（后者未实现，仅占位） |
| `OCRFORGE_WEB_EVOLUTION_PATH` | `data/evolution.json` | 演化数据文件 |
| `OCRFORGE_WEB_OCR_WARMUP` | `true` | 启动时是否跑一次 1×1 warm-up |
| `OCRFORGE_WEB_SKIP_OCR` | _(unset)_ | 设为 `1` 可跳过模型加载（用于纯前端联调） |

## 模型不可用时启动

需要先跑 `/api/convert` 与 `/api/evolution` 但暂不加载模型：

```bash
OCRFORGE_WEB_SKIP_OCR=1 conda run -n paddleocr-vl uvicorn ocrforge_web.main:app ...
```

`/api/ocr` 此时返回 503。

## 代码复用

- `services/ocr_service.py` 直接调用 `ocrforge.models.factory.build_model_module` 与
  `PaddleOCRVLModule.apply_parallel` / `generate_page`，不走 hydra `prepare_run`
  （手工拼最小 `DictConfig`，避免运行目录污染）。
- `ocrforge_web/__init__.py` 在导入时把 `CultureCourse/src` 加入 `sys.path`，
  与 `tools/_bootstrap.py` 同思路。
