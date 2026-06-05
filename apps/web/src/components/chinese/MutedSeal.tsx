import { cn } from "@/lib/cn";

export function MutedSeal({
  label,
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      aria-hidden
      className={cn(
        "absolute top-3 right-3 w-9 h-9 border border-accent/70 text-accent/80",
        "flex items-center justify-center font-serif text-xs",
        "transition-colors duration-300 hover:bg-accent hover:text-surface",
        className,
      )}
    >
      {label ?? "印"}
    </div>
  );
}
