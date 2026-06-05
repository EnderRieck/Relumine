import { cn } from "@/lib/cn";

/**
 * 双弦纹 —— 两条平行 1px 古铜金细线。
 * 入场时左右同时拉伸（origin-center + scaleX 0→1），呈"墨线展开"。
 */
export function YuweiOrnament({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("flex flex-col justify-center text-accent-gold", className)}
    >
      <div
        className="h-px bg-current origin-center animate-line-draw-x"
        style={{ animationDelay: "120ms" }}
      />
      <div className="h-[3px]" />
      <div
        className="h-px bg-current opacity-60 origin-center animate-line-draw-x"
        style={{ animationDelay: "260ms" }}
      />
    </div>
  );
}
