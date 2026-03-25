"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

/**
 * Lightweight markdown renderer for ESG narrative fields.
 *
 * Supports: **bold**, *italic*, `code`, - lists, 1. ordered lists,
 * ## headings, [links](url), and line breaks.
 *
 * No external dependencies — just regex-based HTML conversion.
 * Sanitized: no raw HTML passthrough.
 */

function markdownToHtml(md: string): string {
  let html = md
    // Escape HTML entities
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // Headings (## and ###)
    .replace(/^### (.+)$/gm, '<h4 class="text-sm font-semibold mt-3 mb-1">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="text-base font-semibold mt-4 mb-1">$1</h3>')
    // Bold + italic
    .replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>")
    // Bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Italic
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-slate-100 px-1 py-0.5 rounded text-xs font-mono">$1</code>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
    // Links [text](url)
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" class="text-cyan-600 underline" target="_blank" rel="noopener noreferrer">$1</a>'
    )
    // Line breaks (double newline = paragraph break)
    .replace(/\n\n/g, '</p><p class="mt-2">')
    // Single newline = <br>
    .replace(/\n/g, "<br />");

  // Wrap consecutive <li> in <ul>
  html = html.replace(
    /(<li class="ml-4 list-disc">.*?<\/li>(?:\s*<br \/>)?)+/g,
    (match) => `<ul class="my-1">${match.replace(/<br \/>/g, "")}</ul>`
  );
  html = html.replace(
    /(<li class="ml-4 list-decimal">.*?<\/li>(?:\s*<br \/>)?)+/g,
    (match) => `<ol class="my-1">${match.replace(/<br \/>/g, "")}</ol>`
  );

  return `<p>${html}</p>`;
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  const html = useMemo(() => markdownToHtml(content), [content]);

  return (
    <div
      className={cn("prose prose-sm prose-slate max-w-none", className)}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

interface MarkdownTextareaProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
  className?: string;
  /** Show preview panel alongside editor */
  preview?: boolean;
}

export function MarkdownTextarea({
  value,
  onChange,
  placeholder = "Supports **bold**, *italic*, `code`, - lists, [links](url)...",
  rows = 6,
  disabled = false,
  className,
  preview = false,
}: MarkdownTextareaProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm font-mono placeholder:text-slate-400 focus:border-cyan-300 focus:outline-none focus:ring-1 focus:ring-cyan-300 disabled:opacity-50"
      />
      {preview && value && (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
          <p className="mb-1 text-xs font-medium text-slate-400">Preview</p>
          <MarkdownRenderer content={value} />
        </div>
      )}
    </div>
  );
}
