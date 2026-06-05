/**
 * 回纹背景 — 古铜金细线 SVG pattern, 半透明铺底。
 * 远看是纯米白，近看才显纹饰。固定定位，不随滚动移动。
 */
export function BgPattern() {
  return (
    <div
      aria-hidden
      className="fixed inset-0 z-0 pointer-events-none text-accent-gold"
      style={{ opacity: 0.08 }}
    >
      <svg className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern
            id="huiwen-bg"
            x="0"
            y="0"
            width="64"
            height="64"
            patternUnits="userSpaceOnUse"
          >
            {/* 左下 hook */}
            <path
              d="M 8 56 L 8 28 L 36 28 L 36 48 L 18 48"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
              strokeLinejoin="miter"
            />
            {/* 右上 hook，方向相反，构成交错回纹 */}
            <path
              d="M 56 8 L 56 36 L 28 36 L 28 16 L 46 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1"
              strokeLinejoin="miter"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#huiwen-bg)" />
      </svg>
    </div>
  );
}
