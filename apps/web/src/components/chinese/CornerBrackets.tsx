/**
 * 卡片四角的古籍版心式角花 —— 1px 古铜金细线 L 形。
 * 入场时四角顺时针淡入：左上 → 右上 → 右下 → 左下，
 * 给人"印章四角依次落下"的稳重感。
 */
const STROKE = "text-accent-gold/70";

export function CornerBrackets() {
  return (
    <>
      <svg
        aria-hidden
        viewBox="0 0 14 14"
        className={`absolute top-2 left-2 w-3.5 h-3.5 pointer-events-none animate-fade-in ${STROKE}`}
        style={{ animationDelay: "120ms" }}
      >
        <path
          d="M 0 7 L 0 0 L 7 0"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        />
      </svg>
      <svg
        aria-hidden
        viewBox="0 0 14 14"
        className={`absolute top-2 right-2 w-3.5 h-3.5 pointer-events-none animate-fade-in ${STROKE}`}
        style={{ animationDelay: "220ms" }}
      >
        <path
          d="M 7 0 L 14 0 L 14 7"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        />
      </svg>
      <svg
        aria-hidden
        viewBox="0 0 14 14"
        className={`absolute bottom-2 right-2 w-3.5 h-3.5 pointer-events-none animate-fade-in ${STROKE}`}
        style={{ animationDelay: "320ms" }}
      >
        <path
          d="M 14 7 L 14 14 L 7 14"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        />
      </svg>
      <svg
        aria-hidden
        viewBox="0 0 14 14"
        className={`absolute bottom-2 left-2 w-3.5 h-3.5 pointer-events-none animate-fade-in ${STROKE}`}
        style={{ animationDelay: "420ms" }}
      >
        <path
          d="M 0 7 L 0 14 L 7 14"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
        />
      </svg>
    </>
  );
}
