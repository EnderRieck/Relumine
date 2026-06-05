"use client";

import { useCallback, useRef, useState } from "react";
import { cn } from "@/lib/cn";

type Props = {
  accept?: string;
  onFile: (file: File) => void;
  disabled?: boolean;
  className?: string;
};

export function UploadDropzone({
  accept = "image/jpeg,image/png,image/webp",
  onFile,
  disabled,
  className,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onFile(file);
      e.target.value = "";
    },
    [onFile],
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (disabled) return;
        const file = e.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      aria-disabled={disabled}
      tabIndex={0}
      onKeyDown={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      className={cn(
        "group relative w-full cursor-pointer select-none",
        "border border-dashed transition-colors duration-200",
        "px-8 py-14 text-center",
        over ? "border-accent/60 bg-accent/[0.03]" : "border-line hover:border-accent/40",
        disabled && "opacity-50 cursor-not-allowed",
        className,
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={onChange}
        disabled={disabled}
      />
      <div className="font-serif text-base text-ink tracking-[0.08em]">
        拖入图片，或点击选择
      </div>
      <div className="mt-2 font-sans text-xs text-ink-mute tracking-wider uppercase">
        JPG · PNG · WebP
      </div>
    </div>
  );
}
