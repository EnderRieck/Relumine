import { cn } from "@/lib/cn";

export function HairLine({ className }: { className?: string }) {
  return <div aria-hidden className={cn("h-px w-full bg-line", className)} />;
}
