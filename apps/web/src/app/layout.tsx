import type { Metadata } from "next";
import Image from "next/image";
import { Noto_Serif_SC, Inter } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";
import { BgPattern } from "@/components/chinese/BgPattern";
import { HuiwenKnot } from "@/components/chinese/HuiwenKnot";
import { BrushStroke } from "@/components/chinese/BrushStroke";
import { SealStamp } from "@/components/chinese/SealStamp";
import { PageBridgeProvider } from "@/lib/agent-bridge";
import { AgentShell } from "@/components/agent/agent-shell";

const songti = Noto_Serif_SC({
  variable: "--font-song",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "古籍重光 · CultureCourse",
  description:
    "繁简通译 · 古籍识读 · 形声流变 ——— PaddleOCR-VL 微调成果演示",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="zh-Hans"
      className={`${songti.variable} ${inter.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full bg-bg text-ink font-serif">
        {/* 浮雕级回纹暗纹 —— 不参与文档流，固定不滚 */}
        <BgPattern />

        <PageBridgeProvider>
         <AgentShell>
          <div className="relative z-10 min-h-screen flex flex-col">
            <header className="border-b border-line/80 bg-surface/72 backdrop-blur-md shadow-[0_10px_32px_rgba(57,37,18,0.06)]">
            <div className="mx-auto max-w-[1480px] px-6 md:px-10 h-[4.5rem] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <span className="absolute -inset-1 border border-accent-gold/45" aria-hidden />
                  <Image
                    src="/logo.png"
                    alt="古籍重光 logo"
                    width={46}
                    height={46}
                    priority
                    className="relative h-[2.875rem] w-[2.875rem] object-contain bg-surface"
                  />
                </div>
                <span className="hero-title text-xl font-semibold tracking-[0.18em]">古籍重光</span>
                <span className="hidden sm:inline-flex border-l border-line pl-3 text-xs text-ink-mute font-sans tracking-widest uppercase">
                  北邮学生项目组
                </span>
              </div>
              <nav className="hidden md:flex items-center gap-5 text-xs text-ink-mute font-sans tracking-wider uppercase">
                <span className="text-accent">赵海英老师指导</span>
                <span>·</span>
                <span className="text-[#2f7b67]">文化计算大脑</span>
                <span>·</span>
                <span className="text-[#2f5f8f]">繁简 · OCR · 史脉</span>
              </nav>
            </div>
          </header>

          <main className="flex-1">{children}</main>

          <footer className="border-t border-line/80 bg-surface/70 backdrop-blur-md">
            <div className="mx-auto max-w-[1480px] px-6 md:px-10 py-6 flex flex-col items-center gap-3">
              <div className="flex items-center gap-3 text-ink-soft">
                <BrushStroke className="h-3 w-20 rotate-180 opacity-50" />
                <HuiwenKnot className="w-40 h-3 opacity-80" />
                <BrushStroke className="h-3 w-20 opacity-50" />
              </div>
              <div className="flex items-center gap-3">
                <SealStamp chars={["重", "光"]} size={34} animate={false} className="opacity-90" />
                <div className="text-xs text-ink-mute font-sans tracking-wider">
                  文化表示与挖掘 · 课程展示 · 繁-简数据库 与 古籍OCR识别
                </div>
              </div>
            </div>
          </footer>
          </div>
         </AgentShell>
        </PageBridgeProvider>

        <Toaster
          position="top-center"
          toastOptions={{
            style: {
              background: "var(--color-surface)",
              color: "var(--color-ink)",
              border: "1px solid var(--color-line)",
              borderRadius: "var(--radius)",
              fontFamily: "var(--font-serif)",
            },
          }}
        />
      </body>
    </html>
  );
}
