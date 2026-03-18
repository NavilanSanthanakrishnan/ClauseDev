import type { ReactNode } from 'react';

type Props = {
  content: string;
  className?: string;
};

/** Render inline markdown: **bold**, *italic*, `code` */
function renderInline(text: string): ReactNode {
  const regex = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g;
  const parts = text.split(regex);
  if (parts.length === 1) return text;
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**'))
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        if (part.startsWith('*') && part.endsWith('*'))
          return <em key={i}>{part.slice(1, -1)}</em>;
        if (part.startsWith('`') && part.endsWith('`'))
          return <code key={i} className="md-inline-code">{part.slice(1, -1)}</code>;
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}

/**
 * Lightweight markdown renderer – no external dependencies.
 * Handles headings, bold/italic/code, bullet lists, numbered lists,
 * fenced code blocks, and horizontal rules.
 */
export function MarkdownRenderer({ content, className }: Props) {
  if (!content?.trim()) return null;

  const nodes: ReactNode[] = [];
  const lines = content.split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // ── fenced code block ──────────────────────────────────────────
    if (line.startsWith('```')) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      nodes.push(
        <pre key={`pre-${i}`} className="md-pre">
          <code>{codeLines.join('\n')}</code>
        </pre>,
      );
      i++;
      continue;
    }

    // ── headings ───────────────────────────────────────────────────
    if (line.startsWith('### ')) {
      nodes.push(<h3 key={i} className="md-h3">{renderInline(line.slice(4))}</h3>);
      i++; continue;
    }
    if (line.startsWith('## ')) {
      nodes.push(<h2 key={i} className="md-h2">{renderInline(line.slice(3))}</h2>);
      i++; continue;
    }
    if (line.startsWith('# ')) {
      nodes.push(<h1 key={i} className="md-h1">{renderInline(line.slice(2))}</h1>);
      i++; continue;
    }

    // ── horizontal rule ────────────────────────────────────────────
    if (/^---+$/.test(line.trim())) {
      nodes.push(<hr key={i} className="md-hr" />);
      i++; continue;
    }

    // ── unordered list ─────────────────────────────────────────────
    if (/^[-*] /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*] /.test(lines[i])) {
        items.push(lines[i].slice(2));
        i++;
      }
      nodes.push(
        <ul key={`ul-${i}`} className="md-ul">
          {items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}
        </ul>,
      );
      continue;
    }

    // ── ordered list ───────────────────────────────────────────────
    if (/^\d+\. /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\. /, ''));
        i++;
      }
      nodes.push(
        <ol key={`ol-${i}`} className="md-ol">
          {items.map((item, j) => <li key={j}>{renderInline(item)}</li>)}
        </ol>,
      );
      continue;
    }

    // ── blank line ─────────────────────────────────────────────────
    if (line.trim() === '') { i++; continue; }

    // ── paragraph ──────────────────────────────────────────────────
    nodes.push(<p key={i} className="md-p">{renderInline(line)}</p>);
    i++;
  }

  return (
    <div className={`markdown-rendered${className ? ` ${className}` : ''}`}>
      {nodes}
    </div>
  );
}
