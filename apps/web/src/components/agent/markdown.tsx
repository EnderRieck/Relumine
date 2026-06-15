"use client";

import { memo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/cn";

// Element styling tuned for the narrow assistant column + the site's ink/accent
// design tokens. Tables scroll horizontally so wide ones don't break the layout.
const components: Components = {
  p: ({ children }) => <p className="my-2 leading-relaxed first:mt-0 last:mb-0">{children}</p>,
  h1: ({ children }) => (
    <h1 className="mt-3 mb-2 font-serif text-base font-semibold tracking-wide text-ink">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-3 mb-1.5 font-serif text-[15px] font-semibold tracking-wide text-ink">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-2.5 mb-1 font-serif text-sm font-semibold text-ink">{children}</h3>
  ),
  ul: ({ children }) => <ul className="my-2 ml-4 list-disc space-y-1 marker:text-ink-mute">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 ml-4 list-decimal space-y-1 marker:text-ink-mute">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
    >
      {children}
    </a>
  ),
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-accent/40 pl-3 text-ink-soft">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-3 border-line" />,
  code: ({ className, children, ...props }) => {
    const inline = !className?.includes("language-");
    if (inline) {
      return (
        <code
          className="rounded bg-bg px-1 py-0.5 font-mono text-[0.85em] text-accent"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={cn("font-mono text-xs", className)} {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-[var(--radius)] border border-line bg-bg p-3 text-xs leading-relaxed">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-bg">{children}</thead>,
  th: ({ children }) => (
    <th className="border border-line px-2 py-1 text-left font-semibold text-ink">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border border-line px-2 py-1 align-top text-ink-soft">{children}</td>
  ),
};

export const Markdown = memo(function Markdown({ children }: { children: string }) {
  return (
    <div className="text-sm text-ink break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
});
