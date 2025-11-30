import { useQuery } from "@tanstack/react-query";

import { getPreview } from "../api/client";
import { queryKeys } from "../api/queryKeys";

interface PreviewPaneProps {
  path: string;
}

const HTML_MIME_RE = /html/i;
const TEXT_MIME_RE = /(text|json|xml|yaml|toml)/i;

// Función para detectar el tipo de archivo por extensión
function getFileExtension(path: string): string {
  const match = path.match(/\.([^.]+)$/);
  return match ? match[1].toLowerCase() : "";
}

// Syntax highlighter simple para Python
function highlightPython(code: string): JSX.Element[] {
  const result: JSX.Element[] = [];
  let lineIndex = 0;

  // Primero, identificamos todas las regiones de strings multilínea
  const tripleQuoteRegions: Array<{ start: number; end: number }> = [];
  let match;
  const tripleQuoteRegex = /"""[\s\S]*?"""|'''[\s\S]*?'''/g;

  while ((match = tripleQuoteRegex.exec(code)) !== null) {
    tripleQuoteRegions.push({ start: match.index, end: match.index + match[0].length });
  }

  // Función auxiliar para verificar si una posición está dentro de un docstring
  const isInDocstring = (pos: number): boolean => {
    return tripleQuoteRegions.some(region => pos >= region.start && pos < region.end);
  };

  const lines = code.split("\n");
  let charPos = 0;

  lines.forEach((line, idx) => {
    const lineStart = charPos;
    const lineEnd = charPos + line.length;
    const parts: JSX.Element[] = [];
    let keyIndex = 0;

    // Si toda la línea está en un docstring
    const lineInDocstring = tripleQuoteRegions.some(
      region => lineStart >= region.start && lineEnd <= region.end
    );

    if (lineInDocstring) {
      result.push(
        <div key={idx}>
          <span style={{ color: "#ce9178" }}>{line}</span>
        </div>
      );
      charPos = lineEnd + 1; // +1 para el \n
      return;
    }

    // Detectar comentarios
    if (line.match(/^\s*#/)) {
      result.push(
        <div key={idx}>
          <span style={{ color: "#6a9955" }}>{line}</span>
        </div>
      );
      charPos = lineEnd + 1;
      return;
    }

    // Procesar la línea buscando keywords, strings simples, etc.
    let remaining = line;
    let currentPos = 0;

    // Regex para keywords, strings de una línea y comentarios
    const tokenRegex = /\b(def|class|import|from|as|if|elif|else|for|while|try|except|finally|with|return|yield|raise|assert|pass|break|continue|lambda|async|await|in|is|not|and|or|True|False|None)\b|(['"]).+?\2|#.*/g;

    let tokenMatch;
    while ((tokenMatch = tokenRegex.exec(remaining)) !== null) {
      const before = remaining.substring(currentPos, tokenMatch.index);
      if (before) {
        // Procesar nombres de funciones/clases en el texto antes del token
        const beforeWithHighlight = before.replace(
          /\b(def|class)\s+(\w+)/g,
          (m, kw, name) => {
            parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#c586c0" }}>{kw}</span>);
            parts.push(<span key={`${idx}-${keyIndex++}`}> </span>);
            parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#dcdcaa" }}>{name}</span>);
            return "";
          }
        );

        if (beforeWithHighlight === before) {
          parts.push(<span key={`${idx}-${keyIndex++}`}>{before}</span>);
        }
      }

      const [fullMatch, keyword, quote] = tokenMatch;

      if (keyword) {
        parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#c586c0" }}>{fullMatch}</span>);
      } else if (quote) {
        parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#ce9178" }}>{fullMatch}</span>);
      } else {
        parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#6a9955" }}>{fullMatch}</span>);
      }

      currentPos = tokenMatch.index + fullMatch.length;
    }

    // Agregar el resto de la línea
    const rest = remaining.substring(currentPos);
    if (rest) {
      const restWithHighlight = rest.replace(
        /\b(def|class)\s+(\w+)/g,
        (m, kw, name) => {
          parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#c586c0" }}>{kw}</span>);
          parts.push(<span key={`${idx}-${keyIndex++}`}> </span>);
          parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#dcdcaa" }}>{name}</span>);
          return "";
        }
      );

      if (restWithHighlight === rest) {
        parts.push(<span key={`${idx}-${keyIndex++}`}>{rest}</span>);
      }
    }

    result.push(<div key={idx}>{parts.length > 0 ? parts : line}</div>);
    charPos = lineEnd + 1;
  });

  return result;
}

// Syntax highlighter simple para TypeScript/JavaScript
function highlightTypeScript(code: string): JSX.Element[] {
  const lines = code.split("\n");
  return lines.map((line, idx) => {
    const parts: JSX.Element[] = [];
    let remaining = line;
    let keyIndex = 0;

    // Detectar comentarios de línea
    if (remaining.match(/^\s*\/\//)) {
      return (
        <div key={idx}>
          <span style={{ color: "#6a9955" }}>{line}</span>
        </div>
      );
    }

    // Procesar keywords, strings y comentarios
    let currentPos = 0;
    remaining.replace(
      /\b(function|const|let|var|class|import|export|from|as|if|else|for|while|try|catch|finally|return|async|await|new|this|interface|type|enum|public|private|protected|static)\b|(['"`]).+?\2|\/\/.*/g,
      (match, keyword, quote, offset) => {
        const before = remaining.substring(currentPos, offset);
        if (before) parts.push(<span key={`${idx}-${keyIndex++}`}>{before}</span>);

        if (keyword) {
          parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#569cd6" }}>{match}</span>);
        } else if (quote) {
          parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#ce9178" }}>{match}</span>);
        } else {
          parts.push(<span key={`${idx}-${keyIndex++}`} style={{ color: "#6a9955" }}>{match}</span>);
        }

        currentPos = offset + match.length;
        return "";
      }
    );

    const rest = remaining.substring(currentPos);
    if (rest) parts.push(<span key={`${idx}-${keyIndex++}`}>{rest}</span>);

    return <div key={idx}>{parts.length > 0 ? parts : line}</div>;
  });
}

export function PreviewPane({ path }: PreviewPaneProps): JSX.Element | null {
  const previewQuery = useQuery({
    queryKey: queryKeys.preview(path),
    queryFn: () => getPreview(path),
    enabled: Boolean(path),
  });

  if (!path) {
    return null;
  }

  if (previewQuery.isLoading) {
    return <p style={{ color: "#7f869d", fontSize: "13px" }}>Loading preview…</p>;
  }

  if (previewQuery.isError) {
    return (
      <div className="error-banner">
        Could not load the preview: {String(previewQuery.error)}
      </div>
    );
  }

  const content = previewQuery.data?.content ?? "";
  const contentType = previewQuery.data?.contentType ?? "";
  const isHtml = HTML_MIME_RE.test(contentType);
  const isTextual = TEXT_MIME_RE.test(contentType);

  if (isHtml) {
    return (
      <iframe
        className="preview-frame"
        sandbox="allow-scripts allow-same-origin"
        srcDoc={content}
        title={`Preview of ${path}`}
      />
    );
  }

  if (isTextual) {
    const ext = getFileExtension(path);
    let highlightedContent: JSX.Element[] | null = null;

    // Aplicar syntax highlighting según el tipo de archivo
    if (ext === "py") {
      highlightedContent = highlightPython(content);
    } else if (["ts", "tsx", "js", "jsx"].includes(ext)) {
      highlightedContent = highlightTypeScript(content);
    }

    return (
      <pre className="preview-plain" data-testid="preview-plain" style={{
        fontFamily: "Consolas, 'Courier New', monospace",
        fontSize: "13px",
        lineHeight: "1.6"
      }}>
        {highlightedContent || content}
      </pre>
    );
  }

  return (
    <p className="preview-fallback">
      No preview available for this file type ({contentType || "unknown"}).
    </p>
  );
}
