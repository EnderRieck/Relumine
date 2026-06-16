import { cn } from "@/lib/cn";

/**
 * 朱砂印章 —— 方寸红印，白文（字镂空见纸）。
 * 默认竖排两字「重光」，可传入任意 1–4 字。边缘以 turbulence 做"盖印不匀、
 * 四角微残"的金石气；落印用 seal-press 动画自上压下，略带四度倾斜。
 */
export function SealStamp({
  chars = ["重", "光"],
  size = 64,
  className,
  animate = true,
  title,
}: {
  chars?: string[];
  size?: number;
  className?: string;
  animate?: boolean;
  title?: string;
}) {
  const cols = chars.length <= 1 ? 1 : 2;
  return (
    <div
      className={cn(
        "seal-stamp grid place-items-center gap-0 rounded-[3px]",
        animate && "animate-seal-press",
        className,
      )}
      style={{
        width: size,
        height: size,
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        padding: size * 0.1,
      }}
      role="img"
      aria-label={title ?? `印章 ${chars.join("")}`}
    >
      {chars.map((c, i) => (
        <span
          key={i}
          className="flex items-center justify-center font-serif font-semibold leading-none"
          style={{ fontSize: cols === 1 ? size * 0.52 : size * 0.36 }}
        >
          {c}
        </span>
      ))}
    </div>
  );
}
