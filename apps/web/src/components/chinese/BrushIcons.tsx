import type { SVGProps } from "react";
import { cn } from "@/lib/cn";

/**
 * 写意线描图标 —— 圆头笔触、约 1.6 线宽，与宋体字气质相合，
 * 取代通用 UI 图标库的冷硬感。统一用 currentColor 取色。
 */
type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Base({ size = 22, className, children, ...rest }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={cn(className)}
      {...rest}
    >
      {children}
    </svg>
  );
}

/** 繁简通译 —— 双向回环的转写之意 */
export function IconConvert(p: IconProps) {
  return (
    <Base {...p}>
      <path d="M4 8h11l-2.4-2.6" />
      <path d="M20 16H9l2.4 2.6" />
    </Base>
  );
}

/** 古籍识读 —— 展卷与一束识读之光 */
export function IconScroll(p: IconProps) {
  return (
    <Base {...p}>
      <path d="M6 4h9a2 2 0 0 1 2 2v12a2 2 0 0 0 2 2H8a2 2 0 0 1-2-2V4z" />
      <path d="M6 4a2 2 0 0 0-2 2v0a2 2 0 0 0 2 2" />
      <path d="M9 9h5M9 12.5h5" />
    </Base>
  );
}

/** 形声流变 —— 字源分支演化 */
export function IconBranch(p: IconProps) {
  return (
    <Base {...p}>
      <circle cx="6" cy="6" r="2" />
      <circle cx="18" cy="6" r="2" />
      <circle cx="12" cy="18" r="2" />
      <path d="M6 8v3a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8" />
      <path d="M12 13v3" />
    </Base>
  );
}

/** 史脉 —— 人物地点关系的经络网 */
export function IconMeridian(p: IconProps) {
  return (
    <Base {...p}>
      <circle cx="12" cy="12" r="2.2" />
      <circle cx="5" cy="5.5" r="1.6" />
      <circle cx="19" cy="6" r="1.6" />
      <circle cx="6" cy="19" r="1.6" />
      <circle cx="18.5" cy="18" r="1.6" />
      <path d="M10.4 10.4 6.2 6.6M13.7 10.5 17.6 7M10.5 13.6 7.3 17.6M13.6 13.6 17 16.8" />
    </Base>
  );
}

/** 毛笔 —— 落款/书写意象 */
export function IconBrush(p: IconProps) {
  return (
    <Base {...p}>
      <path d="M17 3.5 20.5 7 12 15.5l-3.5-3.5L17 3.5z" />
      <path d="M8.5 12 5 15.5c-1 1-1.2 3-1.5 4.5 1.5-.3 3.5-.5 4.5-1.5L11.5 15" />
    </Base>
  );
}

/** 印章 —— 钤印意象 */
export function IconSeal(p: IconProps) {
  return (
    <Base {...p}>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M9 9h6v6H9z" />
    </Base>
  );
}
