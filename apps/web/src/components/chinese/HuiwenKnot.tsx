import { cn } from "@/lib/cn";

/**
 * 回纹结 —— 居中一截连续回纹，左右各一条 1px 古铜金细线收尾。
 * 用于 footer 的居中点缀。
 */
export function HuiwenKnot({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 160 14"
      className={cn("text-accent-gold", className)}
    >
      <line x1="0" y1="7" x2="48" y2="7" stroke="currentColor" strokeWidth="1" opacity="0.6" />
      <line x1="112" y1="7" x2="160" y2="7" stroke="currentColor" strokeWidth="1" opacity="0.6" />

      {/* 居中回纹结 64×14：左右两个相向的钩形 */}
      <g transform="translate(48 0)">
        {/* 左钩 */}
        <path
          d="M 4 11 L 4 3 L 14 3 L 14 11 L 8 11"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        />
        {/* 右钩 */}
        <path
          d="M 60 3 L 60 11 L 50 11 L 50 3 L 56 3"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        />
        {/* 中线 */}
        <line x1="18" y1="7" x2="46" y2="7" stroke="currentColor" strokeWidth="1" />
      </g>
    </svg>
  );
}
