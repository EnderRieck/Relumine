import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ConvertPanel } from "@/components/tabs/convert-panel";
import { OcrPanel } from "@/components/tabs/ocr-panel";
import { EvolutionPanel } from "@/components/tabs/evolution-panel";
import { YuweiOrnament } from "@/components/chinese/YuweiOrnament";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-6 md:px-10 py-10 md:py-14">
      <div className="mb-10 md:mb-14 flex flex-col items-start">
        <div className="inline-flex flex-col items-stretch">
          <h1
            className="font-serif text-3xl md:text-4xl tracking-[0.08em] text-ink animate-ink-rise"
            style={{ animationDelay: "0ms" }}
          >
            古籍重光
          </h1>
          <YuweiOrnament className="mt-3 w-full h-4 opacity-90" />
        </div>
        <p
          className="mt-4 max-w-2xl text-sm md:text-base text-ink-soft leading-relaxed animate-ink-rise"
          style={{ animationDelay: "240ms" }}
        >
          完善现有繁体字典，给出北邮方案 · 以古籍为本微调 PaddleOCR，让刻本重现 · 追溯典型汉字繁简演化
        </p>
      </div>

      <Tabs defaultValue="convert">
        <TabsList
          className="mb-10 animate-ink-rise"
          style={{ animationDelay: "380ms" }}
        >
          <TabsTrigger value="convert" ordinal="壹" label="繁简通译" />
          <TabsTrigger value="ocr" ordinal="貳" label="古籍识读" />
          <TabsTrigger value="evolution" ordinal="參" label="形声流变" />
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
      </Tabs>
    </div>
  );
}
