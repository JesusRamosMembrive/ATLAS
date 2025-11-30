/**
 * MarkdownRenderer
 *
 * Renders markdown content with syntax highlighting for code blocks.
 * Used by ClaudeAgentView to display formatted responses.
 */

import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Highlight, themes } from "prism-react-renderer";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={`markdown-content ${className ?? ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: CodeBlock,
          pre: ({ children }) => <>{children}</>,
        }}
      >
        {content}
      </ReactMarkdown>
      <style>{markdownStyles}</style>
    </div>
  );
}

interface CodeBlockProps {
  inline?: boolean;
  className?: string;
  children?: React.ReactNode;
}

function CodeBlock({ inline, className, children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const code = String(children).replace(/\n$/, "");
  const match = /language-(\w+)/.exec(className || "");
  const language = match ? match[1] : "";

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  if (inline) {
    return <code className="inline-code">{children}</code>;
  }

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-language">{language || "text"}</span>
        <button
          className="copy-button"
          onClick={handleCopy}
          title={copied ? "Copied!" : "Copy code"}
        >
          {copied ? (
            <CheckIcon />
          ) : (
            <CopyIcon />
          )}
          <span>{copied ? "Copied!" : "Copy"}</span>
        </button>
      </div>
      <Highlight theme={themes.nightOwl} code={code} language={language || "text"}>
        {({ style, tokens, getLineProps, getTokenProps }) => (
          <pre className="code-block" style={{ ...style, margin: 0 }}>
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })}>
                <span className="line-number">{i + 1}</span>
                {line.map((token, key) => (
                  <span key={key} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  );
}

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

const markdownStyles = `
.markdown-content {
  font-size: 14px;
  line-height: 1.6;
  color: #e2e8f0;
}

.markdown-content p {
  margin: 0 0 12px;
}

.markdown-content p:last-child {
  margin-bottom: 0;
}

.markdown-content h1,
.markdown-content h2,
.markdown-content h3,
.markdown-content h4,
.markdown-content h5,
.markdown-content h6 {
  margin: 16px 0 8px;
  font-weight: 600;
  color: #f1f5f9;
}

.markdown-content h1 { font-size: 1.5em; }
.markdown-content h2 { font-size: 1.3em; }
.markdown-content h3 { font-size: 1.1em; }

.markdown-content ul,
.markdown-content ol {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-content li {
  margin: 4px 0;
}

.markdown-content blockquote {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 3px solid #3b82f6;
  background: rgba(59, 130, 246, 0.1);
  color: #94a3b8;
}

.markdown-content a {
  color: #60a5fa;
  text-decoration: none;
}

.markdown-content a:hover {
  text-decoration: underline;
}

.markdown-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}

.markdown-content th,
.markdown-content td {
  padding: 8px 12px;
  border: 1px solid #334155;
  text-align: left;
}

.markdown-content th {
  background: #1e293b;
  font-weight: 600;
}

.markdown-content hr {
  border: none;
  border-top: 1px solid #334155;
  margin: 16px 0;
}

/* Inline code */
.inline-code {
  padding: 2px 6px;
  background: #1e293b;
  border-radius: 4px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.9em;
  color: #f472b6;
}

/* Code block wrapper */
.code-block-wrapper {
  margin: 12px 0;
  border-radius: 8px;
  overflow: hidden;
  background: #011627;
  border: 1px solid #1e293b;
}

.code-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #0d1b2a;
  border-bottom: 1px solid #1e293b;
}

.code-language {
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.copy-button {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: transparent;
  border: 1px solid #334155;
  border-radius: 4px;
  color: #64748b;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.copy-button:hover {
  background: #1e293b;
  color: #e2e8f0;
  border-color: #475569;
}

.copy-button svg {
  flex-shrink: 0;
}

/* Code block */
.code-block {
  padding: 12px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.code-block > div {
  display: table-row;
}

.line-number {
  display: table-cell;
  padding-right: 16px;
  text-align: right;
  color: #475569;
  user-select: none;
  min-width: 32px;
}

/* Task lists (GFM) */
.markdown-content input[type="checkbox"] {
  margin-right: 8px;
}

/* Strikethrough */
.markdown-content del {
  color: #64748b;
}

/* Strong and emphasis */
.markdown-content strong {
  font-weight: 600;
  color: #f1f5f9;
}

.markdown-content em {
  font-style: italic;
}
`;
