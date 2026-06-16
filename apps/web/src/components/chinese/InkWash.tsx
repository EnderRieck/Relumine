import { cn } from "@/lib/cn";

/**
 * 水墨笔触 —— 一笔横扫的写意墨痕，作为标题区的氛围底图。
 * 用 feTurbulence + feDisplacementMap 把规整笔形"揉"出毛糙的墨边与飞白，
 * 再叠两道枯笔细线，呈"运笔将尽、墨色将枯"的书写感。
 * 纯装饰，默认极淡，由父层用 color / opacity 调和。
 */
export function InkWash({
  className,
  seed = 7,
  style,
}: {
  className?: string;
  seed?: number;
  style?: React.CSSProperties;
}) {
  const fid = `ink-rough-${seed}`;
  const gid = `ink-grad-${seed}`;
  return (
    <svg
      aria-hidden
      viewBox="0 0 820 320"
      preserveAspectRatio="xMidYMid meet"
      style={style}
      className={cn("pointer-events-none select-none text-ink", className)}
    >
      <defs>
        <filter id={fid} x="-20%" y="-40%" width="140%" height="180%">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.013 0.05"
            numOctaves="3"
            seed={seed}
            result="noise"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="noise"
            scale="38"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.32" />
          <stop offset="0.5" stopColor="currentColor" stopOpacity="1" />
          <stop offset="0.86" stopColor="currentColor" stopOpacity="0.5" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0.08" />
        </linearGradient>
      </defs>

      <g filter={`url(#${fid})`} fill={`url(#${gid})`}>
        {/* 主笔：起锋—行笔—收锋的横向墨块 */}
        <path d="M 36 168 C 210 120, 470 118, 612 138 C 712 152, 770 158, 792 170 C 768 196, 700 206, 600 206 C 430 208, 210 214, 36 168 Z" />
        {/* 行笔中段的浓墨堆叠 */}
        <path d="M 150 162 C 320 142, 520 144, 660 160 C 540 184, 330 188, 150 162 Z" opacity="0.55" />
      </g>

      {/* 枯笔飞白：两道更细的拖尾，落在主笔之上 */}
      <g filter={`url(#${fid})`} stroke="currentColor" fill="none" strokeLinecap="round">
        <path d="M 120 150 C 320 138, 560 142, 740 158" strokeWidth="2.4" opacity="0.28" />
        <path d="M 180 182 C 360 192, 560 190, 700 178" strokeWidth="1.6" opacity="0.2" />
      </g>
    </svg>
  );
}
