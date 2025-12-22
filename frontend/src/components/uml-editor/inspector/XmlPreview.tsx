/**
 * XmlPreview - Shows XML preview of a UML entity
 *
 * Converts the entity to the semantic XML format
 * optimized for LLM consumption.
 */

import { useMemo } from "react";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type {
  UmlClassDef,
  UmlInterfaceDef,
  UmlEnumDef,
  UmlStructDef,
  UmlMethodDef,
  UmlInterfaceMethodDef,
  UmlAttributeDef,
} from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

type EntityType = "class" | "interface" | "enum" | "struct";
type Entity = UmlClassDef | UmlInterfaceDef | UmlEnumDef | UmlStructDef;

interface XmlPreviewProps {
  entity: Entity;
  entityType: EntityType;
}

function escapeXml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function indent(level: number): string {
  return "  ".repeat(level);
}

function generateClassXml(cls: UmlClassDef): string {
  const lines: string[] = [];

  // Class opening tag
  const attrs: string[] = [`name="${escapeXml(cls.name)}"`];
  if (cls.isAbstract) attrs.push('abstract="true"');
  if (cls.extends) attrs.push(`extends="${escapeXml(cls.extends)}"`);
  lines.push(`<class ${attrs.join(" ")}>`);

  // Description
  if (cls.description) {
    lines.push(`${indent(1)}<description>${escapeXml(cls.description)}</description>`);
  }

  // Implements
  if (cls.implements.length > 0) {
    lines.push(`${indent(1)}<implements>`);
    cls.implements.forEach((iface) => {
      lines.push(`${indent(2)}<interface>${escapeXml(iface)}</interface>`);
    });
    lines.push(`${indent(1)}</implements>`);
  }

  // Attributes
  if (cls.attributes.length > 0) {
    lines.push(`${indent(1)}<attributes>`);
    cls.attributes.forEach((attr) => {
      lines.push(generateAttributeXml(attr, 2));
    });
    lines.push(`${indent(1)}</attributes>`);
  }

  // Methods
  if (cls.methods.length > 0) {
    lines.push(`${indent(1)}<methods>`);
    cls.methods.forEach((method) => {
      lines.push(generateMethodXml(method, 2));
    });
    lines.push(`${indent(1)}</methods>`);
  }

  lines.push(`</class>`);
  return lines.join("\n");
}

function generateInterfaceXml(iface: UmlInterfaceDef): string {
  const lines: string[] = [];

  lines.push(`<interface name="${escapeXml(iface.name)}">`);

  if (iface.description) {
    lines.push(`${indent(1)}<description>${escapeXml(iface.description)}</description>`);
  }

  // Extends
  if (iface.extends.length > 0) {
    lines.push(`${indent(1)}<extends>`);
    iface.extends.forEach((ext) => {
      lines.push(`${indent(2)}<interface>${escapeXml(ext)}</interface>`);
    });
    lines.push(`${indent(1)}</extends>`);
  }

  // Methods
  if (iface.methods.length > 0) {
    lines.push(`${indent(1)}<methods>`);
    iface.methods.forEach((method) => {
      lines.push(generateInterfaceMethodXml(method, 2));
    });
    lines.push(`${indent(1)}</methods>`);
  }

  lines.push(`</interface>`);
  return lines.join("\n");
}

function generateEnumXml(enumDef: UmlEnumDef): string {
  const lines: string[] = [];

  lines.push(`<enum name="${escapeXml(enumDef.name)}">`);

  if (enumDef.description) {
    lines.push(`${indent(1)}<description>${escapeXml(enumDef.description)}</description>`);
  }

  if (enumDef.values.length > 0) {
    lines.push(`${indent(1)}<values>`);
    enumDef.values.forEach((val) => {
      const valueAttr = val.value !== null ? ` value="${escapeXml(String(val.value))}"` : "";
      if (val.description) {
        lines.push(`${indent(2)}<value name="${escapeXml(val.name)}"${valueAttr}>`);
        lines.push(`${indent(3)}<description>${escapeXml(val.description)}</description>`);
        lines.push(`${indent(2)}</value>`);
      } else {
        lines.push(`${indent(2)}<value name="${escapeXml(val.name)}"${valueAttr} />`);
      }
    });
    lines.push(`${indent(1)}</values>`);
  }

  lines.push(`</enum>`);
  return lines.join("\n");
}

function generateStructXml(struct: UmlStructDef): string {
  const lines: string[] = [];

  lines.push(`<struct name="${escapeXml(struct.name)}">`);

  if (struct.description) {
    lines.push(`${indent(1)}<description>${escapeXml(struct.description)}</description>`);
  }

  if (struct.attributes.length > 0) {
    lines.push(`${indent(1)}<fields>`);
    struct.attributes.forEach((attr) => {
      lines.push(generateAttributeXml(attr, 2));
    });
    lines.push(`${indent(1)}</fields>`);
  }

  lines.push(`</struct>`);
  return lines.join("\n");
}

function generateAttributeXml(attr: UmlAttributeDef, level: number): string {
  const lines: string[] = [];
  const attrs: string[] = [
    `name="${escapeXml(attr.name)}"`,
    `type="${escapeXml(attr.type)}"`,
    `visibility="${attr.visibility}"`,
  ];
  if (attr.isStatic) attrs.push('static="true"');
  if (attr.isReadonly) attrs.push('readonly="true"');
  if (attr.defaultValue) attrs.push(`default="${escapeXml(attr.defaultValue)}"`);

  if (attr.description) {
    lines.push(`${indent(level)}<attribute ${attrs.join(" ")}>`);
    lines.push(`${indent(level + 1)}<description>${escapeXml(attr.description)}</description>`);
    lines.push(`${indent(level)}</attribute>`);
  } else {
    lines.push(`${indent(level)}<attribute ${attrs.join(" ")} />`);
  }

  return lines.join("\n");
}

function generateMethodXml(method: UmlMethodDef, level: number): string {
  const lines: string[] = [];
  const attrs: string[] = [
    `name="${escapeXml(method.name)}"`,
    `visibility="${method.visibility}"`,
  ];
  if (method.isStatic) attrs.push('static="true"');
  if (method.isAsync) attrs.push('async="true"');
  if (method.isAbstract) attrs.push('abstract="true"');

  lines.push(`${indent(level)}<method ${attrs.join(" ")}>`);

  if (method.description) {
    lines.push(`${indent(level + 1)}<description>${escapeXml(method.description)}</description>`);
  }

  // Parameters
  if (method.parameters.length > 0) {
    lines.push(`${indent(level + 1)}<parameters>`);
    method.parameters.forEach((param) => {
      const paramAttrs: string[] = [
        `name="${escapeXml(param.name)}"`,
        `type="${escapeXml(param.type)}"`,
      ];
      if (param.isOptional) paramAttrs.push('optional="true"');
      if (param.defaultValue) paramAttrs.push(`default="${escapeXml(param.defaultValue)}"`);

      if (param.description) {
        lines.push(`${indent(level + 2)}<param ${paramAttrs.join(" ")}>`);
        lines.push(`${indent(level + 3)}<description>${escapeXml(param.description)}</description>`);
        lines.push(`${indent(level + 2)}</param>`);
      } else {
        lines.push(`${indent(level + 2)}<param ${paramAttrs.join(" ")} />`);
      }
    });
    lines.push(`${indent(level + 1)}</parameters>`);
  }

  // Return
  if (method.returnType && method.returnType !== "void") {
    if (method.returnDescription) {
      lines.push(`${indent(level + 1)}<returns type="${escapeXml(method.returnType)}">`);
      lines.push(`${indent(level + 2)}<description>${escapeXml(method.returnDescription)}</description>`);
      lines.push(`${indent(level + 1)}</returns>`);
    } else {
      lines.push(`${indent(level + 1)}<returns type="${escapeXml(method.returnType)}" />`);
    }
  }

  // Preconditions
  if (method.preconditions.length > 0) {
    lines.push(`${indent(level + 1)}<preconditions>`);
    method.preconditions.forEach((pre) => {
      lines.push(`${indent(level + 2)}<condition>${escapeXml(pre)}</condition>`);
    });
    lines.push(`${indent(level + 1)}</preconditions>`);
  }

  // Postconditions
  if (method.postconditions.length > 0) {
    lines.push(`${indent(level + 1)}<postconditions>`);
    method.postconditions.forEach((post) => {
      lines.push(`${indent(level + 2)}<condition>${escapeXml(post)}</condition>`);
    });
    lines.push(`${indent(level + 1)}</postconditions>`);
  }

  // Throws
  if (method.throws.length > 0) {
    lines.push(`${indent(level + 1)}<throws>`);
    method.throws.forEach((t) => {
      lines.push(`${indent(level + 2)}<exception type="${escapeXml(t.exception)}">`);
      lines.push(`${indent(level + 3)}<when>${escapeXml(t.when)}</when>`);
      lines.push(`${indent(level + 2)}</exception>`);
    });
    lines.push(`${indent(level + 1)}</throws>`);
  }

  // Hints
  const hasHints =
    method.hints.edgeCases.length > 0 ||
    method.hints.performance.length > 0 ||
    method.hints.style.length > 0 ||
    method.hints.custom.length > 0;

  if (hasHints) {
    lines.push(`${indent(level + 1)}<hints>`);
    if (method.hints.edgeCases.length > 0) {
      lines.push(`${indent(level + 2)}<edge-cases>`);
      method.hints.edgeCases.forEach((h) => {
        lines.push(`${indent(level + 3)}<case>${escapeXml(h)}</case>`);
      });
      lines.push(`${indent(level + 2)}</edge-cases>`);
    }
    if (method.hints.performance.length > 0) {
      lines.push(`${indent(level + 2)}<performance>`);
      method.hints.performance.forEach((h) => {
        lines.push(`${indent(level + 3)}<hint>${escapeXml(h)}</hint>`);
      });
      lines.push(`${indent(level + 2)}</performance>`);
    }
    if (method.hints.style.length > 0) {
      lines.push(`${indent(level + 2)}<style>`);
      method.hints.style.forEach((h) => {
        lines.push(`${indent(level + 3)}<hint>${escapeXml(h)}</hint>`);
      });
      lines.push(`${indent(level + 2)}</style>`);
    }
    if (method.hints.custom.length > 0) {
      lines.push(`${indent(level + 2)}<custom>`);
      method.hints.custom.forEach((h) => {
        lines.push(`${indent(level + 3)}<hint>${escapeXml(h)}</hint>`);
      });
      lines.push(`${indent(level + 2)}</custom>`);
    }
    lines.push(`${indent(level + 1)}</hints>`);
  }

  // Test Cases
  if (method.testCases.length > 0) {
    lines.push(`${indent(level + 1)}<test-cases>`);
    method.testCases.forEach((tc) => {
      lines.push(`${indent(level + 2)}<test name="${escapeXml(tc.name)}" type="${tc.type}">`);
      lines.push(`${indent(level + 3)}<description>${escapeXml(tc.description)}</description>`);
      lines.push(`${indent(level + 2)}</test>`);
    });
    lines.push(`${indent(level + 1)}</test-cases>`);
  }

  lines.push(`${indent(level)}</method>`);
  return lines.join("\n");
}

function generateInterfaceMethodXml(method: UmlInterfaceMethodDef, level: number): string {
  const lines: string[] = [];

  lines.push(`${indent(level)}<method name="${escapeXml(method.name)}">`);

  if (method.description) {
    lines.push(`${indent(level + 1)}<description>${escapeXml(method.description)}</description>`);
  }

  // Parameters
  if (method.parameters.length > 0) {
    lines.push(`${indent(level + 1)}<parameters>`);
    method.parameters.forEach((param) => {
      const paramAttrs: string[] = [
        `name="${escapeXml(param.name)}"`,
        `type="${escapeXml(param.type)}"`,
      ];
      if (param.isOptional) paramAttrs.push('optional="true"');
      if (param.defaultValue) paramAttrs.push(`default="${escapeXml(param.defaultValue)}"`);

      if (param.description) {
        lines.push(`${indent(level + 2)}<param ${paramAttrs.join(" ")}>`);
        lines.push(`${indent(level + 3)}<description>${escapeXml(param.description)}</description>`);
        lines.push(`${indent(level + 2)}</param>`);
      } else {
        lines.push(`${indent(level + 2)}<param ${paramAttrs.join(" ")} />`);
      }
    });
    lines.push(`${indent(level + 1)}</parameters>`);
  }

  // Return
  if (method.returnType && method.returnType !== "void") {
    lines.push(`${indent(level + 1)}<returns type="${escapeXml(method.returnType)}" />`);
  }

  lines.push(`${indent(level)}</method>`);
  return lines.join("\n");
}

export function XmlPreview({ entity, entityType }: XmlPreviewProps): JSX.Element {
  const xml = useMemo(() => {
    switch (entityType) {
      case "class":
        return generateClassXml(entity as UmlClassDef);
      case "interface":
        return generateInterfaceXml(entity as UmlInterfaceDef);
      case "enum":
        return generateEnumXml(entity as UmlEnumDef);
      case "struct":
        return generateStructXml(entity as UmlStructDef);
      default:
        return "<!-- Unknown entity type -->";
    }
  }, [entity, entityType]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(xml);
    } catch (err) {
      console.error("Failed to copy XML:", err);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={labelStyle}>XML Preview</span>
        <button onClick={handleCopy} style={copyButtonStyle}>
          Copy to Clipboard
        </button>
      </div>

      <pre
        style={{
          margin: 0,
          padding: "16px",
          backgroundColor: colors.base.panel,
          borderRadius: "6px",
          border: `1px solid ${borders.default}`,
          fontSize: "12px",
          fontFamily: "monospace",
          color: colors.text.secondary,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          maxHeight: "400px",
        }}
      >
        {xml}
      </pre>

      <div style={{ fontSize: "11px", color: colors.text.muted, marginTop: "4px" }}>
        This XML format is optimized for LLM code generation.
        <br />
        Use it with Claude to generate implementation code.
      </div>
    </div>
  );
}

// Shared styles
const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "11px",
  fontWeight: 600,
  color: DESIGN_TOKENS.colors.text.muted,
  textTransform: "uppercase",
};

const copyButtonStyle: React.CSSProperties = {
  padding: "6px 12px",
  borderRadius: "4px",
  border: "none",
  backgroundColor: DESIGN_TOKENS.colors.primary.main,
  color: DESIGN_TOKENS.colors.contrast.light,
  fontSize: "11px",
  fontWeight: 500,
  cursor: "pointer",
};
