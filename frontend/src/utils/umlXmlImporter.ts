/**
 * UML XML Importer - Parses XML back to UML project structure
 *
 * Converts XML exported by umlXmlExporter back to UmlProjectDef.
 * Used for loading saved projects from XML files.
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
  UmlParameter,
  UmlThrows,
  UmlTestCase,
  UmlEnumValue,
  UmlTargetLanguage,
  UmlVisibility,
  UmlRelationType,
} from "../api/types";

// Generate unique IDs for imported entities
const generateId = () => crypto.randomUUID();

// Helper to get text content from element
function getTextContent(parent: Element, tagName: string): string {
  const el = parent.querySelector(`:scope > ${tagName}`);
  return el?.textContent?.trim() ?? "";
}

// Helper to get attribute or default
function getAttr(el: Element, name: string, defaultValue: string = ""): string {
  return el.getAttribute(name) ?? defaultValue;
}

// Helper to check boolean attribute
function getBoolAttr(el: Element, name: string): boolean {
  const val = el.getAttribute(name);
  return val === "true";
}

// Parse a single parameter
function parseParameter(el: Element): UmlParameter {
  return {
    name: getAttr(el, "name"),
    type: getAttr(el, "type"),
    description: getTextContent(el, "description"),
    isOptional: getBoolAttr(el, "optional"),
    defaultValue: el.getAttribute("default") ?? null,
  };
}

// Parse throws/exception
function parseThrows(el: Element): UmlThrows {
  return {
    exception: getAttr(el, "type"),
    when: getTextContent(el, "when"),
  };
}

// Parse test case
function parseTestCase(el: Element): UmlTestCase {
  return {
    name: getAttr(el, "name"),
    type: getAttr(el, "type", "success") as "success" | "error" | "edge",
    description: getTextContent(el, "description"),
  };
}

// Parse hints
function parseHints(hintsEl: Element | null): UmlMethodDef["hints"] {
  const hints = {
    edgeCases: [] as string[],
    performance: [] as string[],
    style: [] as string[],
    custom: [] as string[],
  };

  if (!hintsEl) return hints;

  // Edge cases
  const edgeCasesEl = hintsEl.querySelector(":scope > edge-cases");
  if (edgeCasesEl) {
    edgeCasesEl.querySelectorAll(":scope > case").forEach((el) => {
      const text = el.textContent?.trim();
      if (text) hints.edgeCases.push(text);
    });
  }

  // Performance
  const performanceEl = hintsEl.querySelector(":scope > performance");
  if (performanceEl) {
    performanceEl.querySelectorAll(":scope > hint").forEach((el) => {
      const text = el.textContent?.trim();
      if (text) hints.performance.push(text);
    });
  }

  // Style
  const styleEl = hintsEl.querySelector(":scope > style");
  if (styleEl) {
    styleEl.querySelectorAll(":scope > hint").forEach((el) => {
      const text = el.textContent?.trim();
      if (text) hints.style.push(text);
    });
  }

  // Custom
  const customEl = hintsEl.querySelector(":scope > custom");
  if (customEl) {
    customEl.querySelectorAll(":scope > hint").forEach((el) => {
      const text = el.textContent?.trim();
      if (text) hints.custom.push(text);
    });
  }

  return hints;
}

// Parse attribute
function parseAttribute(el: Element): UmlAttributeDef {
  return {
    id: generateId(),
    name: getAttr(el, "name"),
    type: getAttr(el, "type"),
    visibility: getAttr(el, "visibility", "private") as UmlVisibility,
    description: getTextContent(el, "description"),
    defaultValue: el.getAttribute("default") ?? null,
    isStatic: getBoolAttr(el, "static"),
    isReadonly: getBoolAttr(el, "readonly"),
  };
}

// Parse class method (full)
function parseMethod(el: Element): UmlMethodDef {
  const parameters: UmlParameter[] = [];
  el.querySelectorAll(":scope > parameters > param").forEach((p) => {
    parameters.push(parseParameter(p));
  });

  const preconditions: string[] = [];
  el.querySelectorAll(":scope > preconditions > condition").forEach((c) => {
    const text = c.textContent?.trim();
    if (text) preconditions.push(text);
  });

  const postconditions: string[] = [];
  el.querySelectorAll(":scope > postconditions > condition").forEach((c) => {
    const text = c.textContent?.trim();
    if (text) postconditions.push(text);
  });

  const throwsList: UmlThrows[] = [];
  el.querySelectorAll(":scope > throws > exception").forEach((e) => {
    throwsList.push(parseThrows(e));
  });

  const testCases: UmlTestCase[] = [];
  el.querySelectorAll(":scope > test-cases > test").forEach((t) => {
    testCases.push(parseTestCase(t));
  });

  const hintsEl = el.querySelector(":scope > hints");
  const hints = parseHints(hintsEl);

  // Get return type
  const returnsEl = el.querySelector(":scope > returns");
  const returnType = returnsEl?.getAttribute("type") ?? "void";
  const returnDescription = returnsEl ? getTextContent(returnsEl, "description") : "";

  return {
    id: generateId(),
    name: getAttr(el, "name"),
    visibility: getAttr(el, "visibility", "public") as UmlVisibility,
    description: getTextContent(el, "description"),
    isStatic: getBoolAttr(el, "static"),
    isAsync: getBoolAttr(el, "async"),
    parameters,
    returnType,
    returnDescription,
    preconditions,
    postconditions,
    throws: throwsList,
    hints,
    testCases,
  };
}

// Parse interface method (simpler)
function parseInterfaceMethod(el: Element): UmlInterfaceMethodDef {
  const parameters: UmlParameter[] = [];
  el.querySelectorAll(":scope > parameters > param, :scope > param").forEach((p) => {
    parameters.push(parseParameter(p));
  });

  const returnsEl = el.querySelector(":scope > returns");
  const returnType = returnsEl?.getAttribute("type") ?? "void";

  return {
    id: generateId(),
    name: getAttr(el, "name"),
    description: getTextContent(el, "description"),
    parameters,
    returnType,
  };
}

// Parse class
function parseClass(el: Element, index: number): UmlClassDef {
  const attributes: UmlAttributeDef[] = [];
  el.querySelectorAll(":scope > attributes > attribute").forEach((a) => {
    attributes.push(parseAttribute(a));
  });

  const methods: UmlMethodDef[] = [];
  el.querySelectorAll(":scope > methods > method").forEach((m) => {
    methods.push(parseMethod(m));
  });

  // Parse implements
  const implementsList: string[] = [];
  el.querySelectorAll(":scope > implements > interface").forEach((i) => {
    const name = i.textContent?.trim();
    if (name) implementsList.push(name);
  });

  return {
    id: generateId(),
    name: getAttr(el, "name"),
    description: getTextContent(el, "description"),
    isAbstract: getBoolAttr(el, "abstract"),
    extends: el.getAttribute("extends") ?? null,
    implements: implementsList,
    attributes,
    methods,
    position: { x: 100 + (index % 4) * 300, y: 100 + Math.floor(index / 4) * 300 },
  };
}

// Parse interface
function parseInterface(el: Element, index: number): UmlInterfaceDef {
  const methods: UmlInterfaceMethodDef[] = [];
  el.querySelectorAll(":scope > methods > method").forEach((m) => {
    methods.push(parseInterfaceMethod(m));
  });

  // Parse extends
  const extendsList: string[] = [];
  el.querySelectorAll(":scope > extends > interface").forEach((i) => {
    const name = i.textContent?.trim();
    if (name) extendsList.push(name);
  });

  return {
    id: generateId(),
    name: getAttr(el, "name"),
    description: getTextContent(el, "description"),
    extends: extendsList,
    methods,
    position: { x: 100 + (index % 4) * 300, y: 100 + Math.floor(index / 4) * 300 },
  };
}

// Parse enum
function parseEnum(el: Element, index: number): UmlEnumDef {
  const values: UmlEnumValue[] = [];
  el.querySelectorAll(":scope > values > value").forEach((v) => {
    const rawValue = v.getAttribute("value");
    values.push({
      name: getAttr(v, "name"),
      description: getTextContent(v, "description"),
      value: rawValue ?? null,
    });
  });

  return {
    id: generateId(),
    name: getAttr(el, "name"),
    description: getTextContent(el, "description"),
    values,
    position: { x: 100 + (index % 4) * 300, y: 100 + Math.floor(index / 4) * 300 },
  };
}

// Parse struct
function parseStruct(el: Element, index: number): UmlStructDef {
  const attributes: UmlAttributeDef[] = [];
  el.querySelectorAll(":scope > fields > attribute").forEach((a) => {
    attributes.push(parseAttribute(a));
  });

  return {
    id: generateId(),
    name: getAttr(el, "name"),
    description: getTextContent(el, "description"),
    attributes,
    position: { x: 100 + (index % 4) * 300, y: 100 + Math.floor(index / 4) * 300 },
  };
}

// Parse relationship
function parseRelationship(el: Element, entityNameToId: Map<string, string>): UmlRelationshipDef | null {
  const fromName = getAttr(el, "from");
  const toName = getAttr(el, "to");

  // Try to resolve names to IDs (the store uses from/to as IDs)
  const fromId = entityNameToId.get(fromName) ?? fromName;
  const toId = entityNameToId.get(toName) ?? toName;

  return {
    id: generateId(),
    type: getAttr(el, "type", "association") as UmlRelationType,
    from: fromId,
    to: toId,
    description: el.textContent?.trim() || getTextContent(el, "description"),
    cardinality: el.getAttribute("cardinality") ?? null,
  };
}

// Parse module
function parseModule(el: Element): UmlModuleDef {
  const classes: UmlClassDef[] = [];
  let entityIndex = 0;
  el.querySelectorAll(":scope > classes > class").forEach((c) => {
    classes.push(parseClass(c, entityIndex++));
  });

  const interfaces: UmlInterfaceDef[] = [];
  el.querySelectorAll(":scope > interfaces > interface").forEach((i) => {
    interfaces.push(parseInterface(i, entityIndex++));
  });

  const enums: UmlEnumDef[] = [];
  el.querySelectorAll(":scope > enums > enum").forEach((e) => {
    enums.push(parseEnum(e, entityIndex++));
  });

  const structs: UmlStructDef[] = [];
  el.querySelectorAll(":scope > structs > struct").forEach((s) => {
    structs.push(parseStruct(s, entityIndex++));
  });

  // Build name → ID map for relationship resolution
  const entityNameToId = new Map<string, string>();
  classes.forEach((c) => entityNameToId.set(c.name, c.id));
  interfaces.forEach((i) => entityNameToId.set(i.name, i.id));
  enums.forEach((e) => entityNameToId.set(e.name, e.id));
  structs.forEach((s) => entityNameToId.set(s.name, s.id));

  const relationships: UmlRelationshipDef[] = [];
  el.querySelectorAll(":scope > relationships > relationship").forEach((r) => {
    const rel = parseRelationship(r, entityNameToId);
    if (rel) relationships.push(rel);
  });

  return {
    id: generateId(),
    name: getAttr(el, "name"),
    description: getTextContent(el, "description"),
    classes,
    interfaces,
    enums,
    structs,
    relationships,
  };
}

export interface ImportResult {
  success: boolean;
  project?: UmlProjectDef;
  error?: string;
}

/**
 * Parse XML string and convert to UmlProjectDef
 */
export function xmlToProject(xmlString: string): ImportResult {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlString, "application/xml");

    // Check for parse errors
    const parseError = doc.querySelector("parsererror");
    if (parseError) {
      return {
        success: false,
        error: `XML Parse Error: ${parseError.textContent}`,
      };
    }

    // Find the root element (uml-project or project)
    const root = doc.querySelector("uml-project") ?? doc.querySelector("project");
    if (!root) {
      return {
        success: false,
        error: "Invalid XML: Missing <uml-project> or <project> root element",
      };
    }

    // Parse project metadata
    const name = getAttr(root, "name", "Imported Project");
    const version = getAttr(root, "version", "1.0.0");
    const language = getAttr(root, "language", "python") as UmlTargetLanguage;
    const description = getTextContent(root, "description");

    // Parse modules
    const modules: UmlModuleDef[] = [];
    root.querySelectorAll(":scope > module").forEach((m) => {
      modules.push(parseModule(m));
    });

    // If no modules found, create a default one
    if (modules.length === 0) {
      modules.push({
        id: generateId(),
        name: "main",
        description: "",
        classes: [],
        interfaces: [],
        enums: [],
        structs: [],
        relationships: [],
      });
    }

    const project: UmlProjectDef = {
      name,
      version,
      description,
      targetLanguage: language,
      modules,
    };

    return {
      success: true,
      project,
    };
  } catch (err) {
    return {
      success: false,
      error: `Import failed: ${err instanceof Error ? err.message : String(err)}`,
    };
  }
}

/**
 * Read XML file and parse to project
 */
export function readXmlFile(file: File): Promise<ImportResult> {
  return new Promise((resolve) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      const content = e.target?.result;
      if (typeof content !== "string") {
        resolve({ success: false, error: "Failed to read file content" });
        return;
      }
      resolve(xmlToProject(content));
    };

    reader.onerror = () => {
      resolve({ success: false, error: "Failed to read file" });
    };

    reader.readAsText(file);
  });
}
