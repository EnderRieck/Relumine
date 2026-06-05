# 古籍重光 · 三服务启动手册（tmux）

整套演示需要同时跑三个进程：

| 名称 | 端口 | 内容 |
|------|------|------|
| **api** | 127.0.0.1:7860 | FastAPI + PaddleOCR-VL 模型（常驻 GPU） |
| **web** | 127.0.0.1:3000 | Next.js 16 dev server（前端） |
| **cf**  | —          | cloudflared 临时隧道，把 :3000 暴露到公网 |

`web` 通过 `next.config.ts` 的 `rewrites` 把 `/api/*` 内部代理到 `:7860`，所以浏览器只看到一个域名。

---

## 一次性启动（复制粘贴）

```bash
# 1) 先确保旧进程不在
pkill -f 'uvicorn ocrforge_web' 2>/dev/null
pkill -f 'next dev'             2>/dev/null
pkill -f 'cloudflared tunnel'   2>/dev/null
sleep 2

# 2) 三个 tmux 会话
tmux new-session -d -s api \
  'conda run -n paddleocr-vl uvicorn ocrforge_web.main:app \
     --host 127.0.0.1 --port 7860 \
     --app-dir /mnt/paper2any/ziyi/CultureCourse/apps/api'

tmux new-session -d -s web \
  'cd /mnt/paper2any/ziyi/CultureCourse/apps/web && \
   npm run dev -- --port 3000 --hostname 127.0.0.1'

tmux new-session -d -s cf \
  'cloudflared tunnel --url http://127.0.0.1:3000 --no-autoupdate'

# 3) 列出当前会话
tmux ls
```

---

## 等模型加载完（~15-20s）

```bash
# 反复轮询直到 model_loaded:true
until curl -s -m 2 http://127.0.0.1:7860/api/healthz | grep -q '"model_loaded":true'; do
  echo "loading..."; sleep 3
done
echo "✓ model ready"
```

---

## 拿公网 URL

```bash
# cloudflared 启动后约 5-15s 才出 URL
tmux capture-pane -t cf -p | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1
```

或者直接 attach 看日志里的"Your quick Tunnel has been created!"那一行：

```bash
tmux attach -t cf
# 看到 URL 后按 Ctrl-b d 退出但保留进程
```

> ⚠️ 临时隧道每次启动 URL 都会变，记得把新 URL 加进 `next.config.ts` 的 `allowedDevOrigins`（已支持通配符 `*.trycloudflare.com`，正常不用动）。

---

## 验证三件套

```bash
URL=https://你的隧道.trycloudflare.com

curl -s $URL/api/healthz                       # {"ok":true,"model_loaded":true,"version":"0.1.0"}
curl -s $URL/api/ocr/queue                     # {"depth":0}
curl -s -X POST $URL/api/convert \
  -H "Content-Type: application/json" \
  -d '{"text":"皇后與發財","direction":"t2s"}'  # collisions 应含 后/发
```

---

## 日常运维

### 看日志

```bash
tmux attach -t api      # 看 OCR 推理 / 模型加载
tmux attach -t web      # 看 Next.js 编译 + HTTP 请求
tmux attach -t cf       # 看隧道连接 / 公网请求量

# 进入会话后：
#   Ctrl-b d  退出但保留运行
#   Ctrl-b [  进入 scroll 模式（PageUp/PageDown 翻历史，q 退出）
```

### 重启单个服务

```bash
# 比如只重启 api（改了 ocr_service.py 之后）
tmux kill-session -t api
tmux new-session -d -s api \
  'conda run -n paddleocr-vl uvicorn ocrforge_web.main:app \
     --host 127.0.0.1 --port 7860 \
     --app-dir /mnt/paper2any/ziyi/CultureCourse/apps/api'
```

> 注意：每次 `tmux kill-session -t cf` 然后重启，公网 URL 都会变。

### 全部停掉

```bash
tmux kill-session -t api 2>/dev/null
tmux kill-session -t web 2>/dev/null
tmux kill-session -t cf  2>/dev/null
tmux ls   # 应为空
```

---

## 故障排查

### 1. `model_loaded:false` 长期不变
- 进 `tmux attach -t api` 看是否 OOM / flash_attention_2 缺失
- 若 flash_attention_2 装不上：临时改 `OCRFORGE_WEB_PADDLE_ATTN=sdpa`
- 若想跳过模型只测前端：`OCRFORGE_WEB_SKIP_OCR=1` 启动

### 2. 公网点 tab 没反应
- 几乎一定是 `allowedDevOrigins` 没覆盖到新隧道域名
- 检查 `apps/web/next.config.ts` 里有 `*.trycloudflare.com`
- 改完一定重启 `web` 会话才生效

### 3. cloudflared 一直在 "Retrying connection"
- 出口 443/QUIC 被防火墙挡了，换 TCP：在命令尾加 `--protocol http2`
- 国内机器有时连 sjc10 慢，可加 `--region us`

### 4. OCR 单卡排队太长
- 当前是 `asyncio.Lock` 串行；多人演示时队列前端会显示"前面有 N 位"
- 若需提速：调大模型 batch / 加更多 GPU，超出本期范围

---

## 文件路径速查

| 用途 | 路径 |
|------|------|
| 后端代码 | `CultureCourse/apps/api/ocrforge_web/` |
| 前端代码 | `CultureCourse/apps/web/src/` |
| 模型 checkpoint | `CultureCourse/runs/train/20260429-152932_train_paddle/checkpoints/step_000200` |
| 演化数据 | `CultureCourse/apps/api/ocrforge_web/data/evolution.json` |
| 后端环境变量配置 | `CultureCourse/apps/api/ocrforge_web/settings.py` |
| Next 配置 | `CultureCourse/apps/web/next.config.ts` |
| 测试图片 | `CultureCourse/datasets/MTH/raw/JPEGImages/01-V001P000D.jpg` |
