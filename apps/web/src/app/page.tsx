import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ConvertPanel } from "@/components/tabs/convert-panel";
import { OcrPanel } from "@/components/tabs/ocr-panel";
import { EvolutionPanel } from "@/components/tabs/evolution-panel";
import { CulturePanel } from "@/components/tabs/culture-panel";
import { YuweiOrnament } from "@/components/chinese/YuweiOrnament";
import { InkWash } from "@/components/chinese/InkWash";
import { HeroContents } from "@/components/chinese/HeroContents";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-[1480px] px-6 md:px-10 py-8 md:py-12">
      <div className="paper-surface chromatic-frame relative mb-8 md:mb-10 grid items-center gap-10 border border-line/80 px-6 py-9 md:grid-cols-[minmax(0,1fr)_400px] md:px-12 md:py-12">
        {/* 水墨氛围底图：一笔横扫，墨色极淡，仅作纸面气韵 */}
        <InkWash
          seed={7}
          className="pointer-events-none absolute -left-8 top-2 z-0 hidden h-[230px] w-[560px] animate-ink-spread md:block"
          style={{ ["--ink-spread-to" as string]: "0.045" }}
        />

        <div className="relative z-10 flex flex-col items-start">
          <div className="eyebrow animate-ink-rise">Classical Chinese · Computational Humanities</div>
          <div className="mt-4 inline-flex flex-col items-stretch">
            <h1
              className="hero-title font-serif text-5xl tracking-[0.14em] md:text-7xl animate-ink-rise"
              style={{ animationDelay: "60ms" }}
            >
              古籍重光
            </h1>
            <YuweiOrnament className="mt-4 w-full h-4 opacity-90" />
          </div>

          <blockquote
            className="epigraph mt-7 max-w-xl font-serif text-base leading-9 tracking-[0.04em] animate-ink-rise"
            style={{ animationDelay: "200ms" }}
          >
            文字者，經藝之本；前人所以垂後，後人所以識古。
            <cite className="mt-1.5 block font-sans text-[11px] not-italic tracking-[0.16em] text-ink-mute">
              ——— 許慎《說文解字 · 敘》
            </cite>
          </blockquote>

          <p
            className="mt-6 max-w-xl text-sm leading-8 text-ink-soft md:text-[15px] animate-ink-rise"
            style={{ animationDelay: "320ms" }}
          >
            以繁简映射数据库为骨架，以古籍 OCR 与文化计算为两翼，把字形、文本与人物关系重新连回可检索、可解释、可复核的知识链。
          </p>
        </div>

        <div className="relative z-10">
          <HeroContents />
        </div>
      </div>

      <Tabs defaultValue="convert">
        <TabsList
          className="mb-10 animate-ink-rise"
          style={{ animationDelay: "380ms" }}
        >
          <TabsTrigger value="convert" ordinal="壹" label="繁简通译" />
          <TabsTrigger value="ocr" ordinal="貳" label="古籍识读" />
          <TabsTrigger value="evolution" ordinal="參" label="形声流变" />
          <TabsTrigger value="culture" ordinal="肆" label="史脉" />
        </TabsList>

        <TabsContent value="convert">
          <ConvertPanel />
        </TabsContent>
        <TabsContent value="ocr">
          <OcrPanel />
        </TabsContent>
        <TabsContent value="evolution">
          <EvolutionPanel />
        </TabsContent>
        <TabsContent value="culture">
          <CulturePanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
