import { cn } from "@/lib/cn";

export function GoldRule({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("h-px w-6 bg-accent-gold opacity-60", className)}
    />
  );
}
