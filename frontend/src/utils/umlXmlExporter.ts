/**
 * UML XML Exporter - Converts UML project to semantic XML
 *
 * Generates XML format optimized for LLM code generation.
 * Follows the AEGIS v2 specification.
 */

import type {
  UmlProjectDef,
  UmlModuleDef,
  UmlClassDef,
  UmlInterfaceDef,
  UmlEnumDef,
  UmlStructDef,
  UmlMethodDef,
  UmlInterfaceMethodDef,
  UmlAttributeDef,
  UmlRelationshipDef,
} from "../api/types";

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

function generateClassXml(cls: UmlClassDef, level: number): string {
  const lines: string[] = [];

  // Class opening tag
  const attrs: string[] = [`name="${escapeXml(cls.name)}"`];
  if (cls.isAbstract) attrs.push('abstract="true"');
  if (cls.extends) attrs.push(`extends="${escapeXml(cls.extends)}"`);
  lines.push(`${indent(level)}<class ${attrs.join(" ")}>`);

  // Description
  if (cls.description) {
    lines.push(`${indent(level + 1)}<description>${escapeXml(cls.description)}</description>`);
  }

  // Implements
  if (cls.implements.length > 0) {
    lines.push(`${indent(level + 1)}<implements>`);
    cls.implements.forEach((iface) => {
      lines.push(`${indent(level + 2)}<interface>${escapeXml(iface)}</interface>`);
    });
    lines.push(`${indent(level + 1)}</implements>`);
  }

  // Attributes
  if (cls.attributes.length > 0) {
    lines.push(`${indent(level + 1)}<attributes>`);
    cls.attributes.forEach((attr) => {
      lines.push(generateAttributeXml(attr, level + 2));
    });
    lines.push(`${indent(level + 1)}</attributes>`);
  }

  // Methods
  if (cls.methods.length > 0) {
    lines.push(`${indent(level + 1)}<methods>`);
    cls.methods.forEach((method) => {
      lines.push(generateMethodXml(method, level + 2));
    });
    lines.push(`${indent(level + 1)}</methods>`);
  }

  lines.push(`${indent(level)}</class>`);
  return lines.join("\n");
}

function generateInterfaceXml(iface: UmlInterfaceDef, level: number): string {
  const lines: string[] = [];

  lines.push(`${indent(level)}<interface name="${escapeXml(iface.name)}">`);

  if (iface.description) {
    lines.push(`${indent(level + 1)}<description>${escapeXml(iface.description)}</description>`);
  }

  // Extends
  if (iface.extends.length > 0) {
    lines.push(`${indent(level + 1)}<extends>`);
    iface.extends.forEach((ext) => {
      lines.push(`${indent(level + 2)}<interface>${escapeXml(ext)}</interface>`);
    });
    lines.push(`${indent(level + 1)}</extends>`);
  }

  // Methods
  if (iface.methods.length > 0) {
    lines.push(`${indent(level + 1)}<methods>`);
    iface.methods.forEach((method) => {
      lines.push(generateInterfaceMethodXml(method, level + 2));
    });
    lines.push(`${indent(level + 1)}</methods>`);
  }

  lines.push(`${indent(level)}</interface>`);
  return lines.join("\n");
}

function generateEnumXml(enumDef: UmlEnumDef, level: number): string {
  const lines: string[] = [];

  lines.push(`${indent(level)}<enum name="${escapeXml(enumDef.name)}">`);

  if (enumDef.description) {
    lines.push(`${indent(level + 1)}<description>${escapeXml(enumDef.description)}</description>`);
  }

  if (enumDef.values.length > 0) {
    lines.push(`${indent(level + 1)}<values>`);
    enumDef.values.forEach((val) => {
      const valueAttr = val.value !== null ? ` value="${escapeXml(String(val.value))}"` : "";
      if (val.description) {
        lines.push(`${indent(level + 2)}<value name="${escapeXml(val.name)}"${valueAttr}>`);
        lines.push(`${indent(level + 3)}<description>${escapeXml(val.description)}</description>`);
        lines.push(`${indent(level + 2)}</value>`);
      } else {
        lines.push(`${indent(level + 2)}<value name="${escapeXml(val.name)}"${valueAttr} />`);
      }
    });
    lines.push(`${indent(level + 1)}</values>`);
  }

  lines.push(`${indent(level)}</enum>`);
  return lines.join("\n");
}

function generateStructXml(struct: UmlStructDef, level: number): string {
  const lines: string[] = [];

  lines.push(`${indent(level)}<struct name="${escapeXml(struct.name)}">`);

  if (struct.description) {
    lines.push(`${indent(level + 1)}<description>${escapeXml(struct.description)}</description>`);
  }

  // Fields (attributes)
  if (struct.attributes.length > 0) {
    lines.push(`${indent(level + 1)}<fields>`);
    struct.attributes.forEach((attr) => {
      lines.push(generateAttributeXml(attr, level + 2));
    });
    lines.push(`${indent(level + 1)}</fields>`);
  }

  lines.push(`${indent(level)}</struct>`);
  return lines.join("\n");
}

function generateRelationshipXml(rel: UmlRelationshipDef, level: number): string {
  const lines: string[] = [];
  const attrs: string[] = [
    `type="${rel.type}"`,
    `from="${escapeXml(rel.from)}"`,
    `to="${escapeXml(rel.to)}"`,
  ];
  if (rel.cardinality) attrs.push(`cardinality="${escapeXml(rel.cardinality)}"`);

  if (rel.description) {
    lines.push(`${indent(level)}<relationship ${attrs.join(" ")}>`);
    lines.push(`${indent(level + 1)}<description>${escapeXml(rel.description)}</description>`);
    lines.push(`${indent(level)}</relationship>`);
  } else {
    lines.push(`${indent(level)}<relationship ${attrs.join(" ")} />`);
  }

  return lines.join("\n");
}

function generateModuleXml(module: UmlModuleDef, level: number): string {
  const lines: string[] = [];

  lines.push(`${indent(level)}<module name="${escapeXml(module.name)}">`);

  if (module.description) {
    lines.push(`${indent(level + 1)}<description>${escapeXml(module.description)}</description>`);
  }

  // Classes
  if (module.classes.length > 0) {
    lines.push(`${indent(level + 1)}<classes>`);
    module.classes.forEach((cls) => {
      lines.push(generateClassXml(cls, level + 2));
    });
    lines.push(`${indent(level + 1)}</classes>`);
  }

  // Interfaces
  if (module.interfaces.length > 0) {
    lines.push(`${indent(level + 1)}<interfaces>`);
    module.interfaces.forEach((iface) => {
      lines.push(generateInterfaceXml(iface, level + 2));
    });
    lines.push(`${indent(level + 1)}</interfaces>`);
  }

  // Enums
  if (module.enums.length > 0) {
    lines.push(`${indent(level + 1)}<enums>`);
    module.enums.forEach((enumDef) => {
      lines.push(generateEnumXml(enumDef, level + 2));
    });
    lines.push(`${indent(level + 1)}</enums>`);
  }

  // Structs
  if (module.structs.length > 0) {
    lines.push(`${indent(level + 1)}<structs>`);
    module.structs.forEach((struct) => {
      lines.push(generateStructXml(struct, level + 2));
    });
    lines.push(`${indent(level + 1)}</structs>`);
  }

  // Relationships
  if (module.relationships.length > 0) {
    lines.push(`${indent(level + 1)}<relationships>`);
    module.relationships.forEach((rel) => {
      lines.push(generateRelationshipXml(rel, level + 2));
    });
    lines.push(`${indent(level + 1)}</relationships>`);
  }

  lines.push(`${indent(level)}</module>`);
  return lines.join("\n");
}

export function projectToXml(project: UmlProjectDef): string {
  const lines: string[] = [];

  lines.push('<?xml version="1.0" encoding="UTF-8"?>');
  lines.push(`<uml-project name="${escapeXml(project.name)}" version="${escapeXml(project.version)}" language="${project.targetLanguage}">`);

  if (project.description) {
    lines.push(`${indent(1)}<description>${escapeXml(project.description)}</description>`);
  }

  // Modules
  project.modules.forEach((module) => {
    lines.push(generateModuleXml(module, 1));
  });

  lines.push("</uml-project>");

  return lines.join("\n");
}

export function moduleToXml(module: UmlModuleDef): string {
  const lines: string[] = [];
  lines.push('<?xml version="1.0" encoding="UTF-8"?>');
  lines.push(generateModuleXml(module, 0));
  return lines.join("\n");
}

// Download XML as file
export function downloadXml(xml: string, filename: string): void {
  const blob = new Blob([xml], { type: "application/xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Copy XML to clipboard
export async function copyXmlToClipboard(xml: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(xml);
    return true;
  } catch (err) {
    console.error("Failed to copy XML to clipboard:", err);
    return false;
  }
}
