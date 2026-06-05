# web · Next.js 前端

「古籍重光」三 Tab 演示界面：繁简通译 / 古籍识读 / 形声流变。

## 启动

```bash
cd CultureCourse/apps/web
npm install
npm run dev -- --port 3000 --hostname 127.0.0.1
```

`next.config.ts` 已配置 `rewrites`，把 `/api/*` 透传到 `http://127.0.0.1:7860`，
所以前端启动前确保 [后端](../api/README.md) 已在 7860 端口运行。

## 设计

- **栈**：Next.js 16 (App Router) + React 19 + Tailwind 4 + TypeScript
- **字体**：Noto Serif SC + Inter，通过 `next/font/google` 在线拉取
- **风格**：新中式极简——纯米白底 (`#f7f5f0`) + 朱砂点缀 (`#9a2a1f`) + 古铜金细线 (`#c2a96a`)，无宣纸纹理、无水墨、无阴影
- **依赖**：仅 `@radix-ui/react-hover-card`、`sonner`、`clsx`，未引 shadcn/ui CLI（Tailwind 4 主题直接在 `globals.css` 用 `@theme` 声明）

## 目录

```
src/
├── app/{layout,page,globals.css}     主壳与首页
├── components/
│   ├── ui/tabs.tsx                   手卷 Tabs（带 React state）
│   ├── chinese/                      SectionMark · HairLine · GoldRule · MutedSeal
│   ├── tabs/                         convert-panel · ocr-panel · evolution-panel
│   └── shared/upload-dropzone.tsx
└── lib/{api,types,cn}.ts
```

## 构建

```bash
npm run build
```

生产部署：`npm run start`（默认 :3000）。
