import { cn } from "@/lib/cn";

/**
 * 墨笔分隔 —— 一道两端出锋、中段饱满的写意横线，替代规整的双弦纹。
 * 可作章节分隔或标题收尾。sweep 时以笔锋自左推出。
 */
export function BrushStroke({
  className,
  sweep = false,
}: {
  className?: string;
  sweep?: boolean;
}) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 240 16"
      preserveAspectRatio="none"
      className={cn(
        "text-ink-soft",
        sweep && "animate-brush-sweep",
        className,
      )}
    >
      <defs>
        <filter id="brush-rough" x="-5%" y="-60%" width="110%" height="220%">
          <feTurbulence type="fractalNoise" baseFrequency="0.02 0.6" numOctaves="2" seed="11" result="n" />
          <feDisplacementMap in="SourceGraphic" in2="n" scale="6" />
        </filter>
      </defs>
      <path
        filter="url(#brush-rough)"
        fill="currentColor"
        d="M 6 8 C 60 4, 120 5, 150 7 C 186 9, 214 7, 234 8 C 214 11, 186 11, 150 10 C 120 11, 60 12, 6 8 Z"
      />
    </svg>
  );
}
