/**
 * UML Validator - Semantic validation for UML models
 *
 * Validates:
 * - Referential integrity (extends/implements point to existing types)
 * - Inheritance cycles
 * - Incomplete methods (missing return type, parameters without type)
 * - Interfaces not fully implemented
 * - Duplicate names
 * - Empty entities
 */

import type {
  UmlProjectDef,
  UmlModuleDef,
  UmlClassDef,
  UmlInterfaceDef,
  UmlEnumDef,
  UmlStructDef,
  UmlValidationError,
  UmlValidationResult,
} from "../api/types";

type ValidationSeverity = "error" | "warning" | "info";

interface ValidationContext {
  allTypeNames: Set<string>;
  classMap: Map<string, UmlClassDef>;
  interfaceMap: Map<string, UmlInterfaceDef>;
  enumMap: Map<string, UmlEnumDef>;
  structMap: Map<string, UmlStructDef>;
}

function buildContext(module: UmlModuleDef): ValidationContext {
  const allTypeNames = new Set<string>();
  const classMap = new Map<string, UmlClassDef>();
  const interfaceMap = new Map<string, UmlInterfaceDef>();
  const enumMap = new Map<string, UmlEnumDef>();
  const structMap = new Map<string, UmlStructDef>();

  module.classes.forEach((cls) => {
    allTypeNames.add(cls.name);
    classMap.set(cls.name, cls);
  });

  module.interfaces.forEach((iface) => {
    allTypeNames.add(iface.name);
    interfaceMap.set(iface.name, iface);
  });

  module.enums.forEach((enumDef) => {
    allTypeNames.add(enumDef.name);
    enumMap.set(enumDef.name, enumDef);
  });

  module.structs.forEach((struct) => {
    allTypeNames.add(struct.name);
    structMap.set(struct.name, struct);
  });

  return { allTypeNames, classMap, interfaceMap, enumMap, structMap };
}

function createError(
  severity: ValidationSeverity,
  code: string,
  message: string,
  entityId: string,
  entityType: "class" | "interface" | "enum" | "struct" | "method" | "attribute" | "relationship",
  field?: string
): UmlValidationError {
  return { severity, code, message, entityId, entityType, field };
}

// Check for duplicate type names
function validateDuplicateNames(module: UmlModuleDef): UmlValidationError[] {
  const errors: UmlValidationError[] = [];
  const seen = new Map<string, { id: string; type: string }>();

  const checkName = (name: string, id: string, type: string) => {
    if (seen.has(name)) {
      const existing = seen.get(name)!;
      errors.push(
        createError(
          "error",
          "DUPLICATE_NAME",
          `Duplicate type name "${name}" (also defined as ${existing.type})`,
          id,
          type as any
        )
      );
    } else {
      seen.set(name, { id, type });
    }
  };

  module.classes.forEach((cls) => checkName(cls.name, cls.id, "class"));
  module.interfaces.forEach((iface) => checkName(iface.name, iface.id, "interface"));
  module.enums.forEach((enumDef) => checkName(enumDef.name, enumDef.id, "enum"));
  module.structs.forEach((struct) => checkName(struct.name, struct.id, "struct"));

  return errors;
}

// Check for inheritance cycles
function detectInheritanceCycle(
  className: string,
  classMap: Map<string, UmlClassDef>,
  visited: Set<string> = new Set()
): string[] | null {
  if (visited.has(className)) {
    return [className];
  }

  const cls = classMap.get(className);
  if (!cls || !cls.extends) {
    return null;
  }

  visited.add(className);
  const cycle = detectInheritanceCycle(cls.extends, classMap, visited);

  if (cycle) {
    cycle.unshift(className);
    return cycle;
  }

  return null;
}

function validateInheritanceCycles(ctx: ValidationContext): UmlValidationError[] {
  const errors: UmlValidationError[] = [];
  const checked = new Set<string>();

  ctx.classMap.forEach((cls) => {
    if (checked.has(cls.name)) return;

    const cycle = detectInheritanceCycle(cls.name, ctx.classMap);
    if (cycle) {
      errors.push(
        createError(
          "error",
          "INHERITANCE_CYCLE",
          `Inheritance cycle detected: ${cycle.join(" -> ")}`,
          cls.id,
          "class",
          "extends"
        )
      );
      cycle.forEach((name) => checked.add(name));
    }
  });

  return errors;
}

// Validate class references
function validateClassReferences(cls: UmlClassDef, ctx: ValidationContext): UmlValidationError[] {
  const errors: UmlValidationError[] = [];

  // Check extends reference
  if (cls.extends && !ctx.classMap.has(cls.extends)) {
    errors.push(
      createError(
        "error",
        "INVALID_EXTENDS",
        `Class "${cls.name}" extends unknown type "${cls.extends}"`,
        cls.id,
        "class",
        "extends"
      )
    );
  }

  // Check implements references
  cls.implements.forEach((ifaceName) => {
    if (!ctx.interfaceMap.has(ifaceName)) {
      errors.push(
        createError(
          "error",
          "INVALID_IMPLEMENTS",
          `Class "${cls.name}" implements unknown interface "${ifaceName}"`,
          cls.id,
          "class",
          "implements"
        )
      );
    }
  });

  return errors;
}

// Validate interface references
function validateInterfaceReferences(
  iface: UmlInterfaceDef,
  ctx: ValidationContext
): UmlValidationError[] {
  const errors: UmlValidationError[] = [];

  iface.extends.forEach((parentName) => {
    if (!ctx.interfaceMap.has(parentName)) {
      errors.push(
        createError(
          "error",
          "INVALID_EXTENDS",
          `Interface "${iface.name}" extends unknown interface "${parentName}"`,
          iface.id,
          "interface",
          "extends"
        )
      );
    }
  });

  return errors;
}

// Validate class completeness
function validateClassCompleteness(cls: UmlClassDef): UmlValidationError[] {
  const errors: UmlValidationError[] = [];

  // Empty class warning
  if (cls.attributes.length === 0 && cls.methods.length === 0) {
    errors.push(
      createError(
        "warning",
        "EMPTY_CLASS",
        `Class "${cls.name}" has no attributes or methods`,
        cls.id,
        "class"
      )
    );
  }

  // Missing description
  if (!cls.description.trim()) {
    errors.push(
      createError(
        "info",
        "MISSING_DESCRIPTION",
        `Class "${cls.name}" has no description`,
        cls.id,
        "class",
        "description"
      )
    );
  }

  // Validate attributes
  cls.attributes.forEach((attr) => {
    if (!attr.type.trim()) {
      errors.push(
        createError(
          "error",
          "MISSING_TYPE",
          `Attribute "${attr.name}" in class "${cls.name}" has no type`,
          cls.id,
          "attribute",
          "type"
        )
      );
    }
  });

  // Validate methods
  cls.methods.forEach((method) => {
    if (!method.returnType.trim()) {
      errors.push(
        createError(
          "warning",
          "MISSING_RETURN_TYPE",
          `Method "${method.name}" in class "${cls.name}" has no return type`,
          cls.id,
          "method",
          "returnType"
        )
      );
    }

    method.parameters.forEach((param) => {
      if (!param.type.trim()) {
        errors.push(
          createError(
            "error",
            "MISSING_PARAM_TYPE",
            `Parameter "${param.name}" in method "${method.name}" has no type`,
            cls.id,
            "method",
            "parameters"
          )
        );
      }
    });

    // Abstract methods in non-abstract class
    if (method.isAbstract && !cls.isAbstract) {
      errors.push(
        createError(
          "error",
          "ABSTRACT_IN_CONCRETE",
          `Abstract method "${method.name}" in non-abstract class "${cls.name}"`,
          cls.id,
          "method",
          "isAbstract"
        )
      );
    }
  });

  return errors;
}

// Validate interface completeness
function validateInterfaceCompleteness(iface: UmlInterfaceDef): UmlValidationError[] {
  const errors: UmlValidationError[] = [];

  if (iface.methods.length === 0) {
    errors.push(
      createError(
        "warning",
        "EMPTY_INTERFACE",
        `Interface "${iface.name}" has no methods`,
        iface.id,
        "interface"
      )
    );
  }

  if (!iface.description.trim()) {
    errors.push(
      createError(
        "info",
        "MISSING_DESCRIPTION",
        `Interface "${iface.name}" has no description`,
        iface.id,
        "interface",
        "description"
      )
    );
  }

  iface.methods.forEach((method) => {
    if (!method.returnType.trim()) {
      errors.push(
        createError(
          "warning",
          "MISSING_RETURN_TYPE",
          `Method "${method.name}" in interface "${iface.name}" has no return type`,
          iface.id,
          "method",
          "returnType"
        )
      );
    }

    method.parameters.forEach((param) => {
      if (!param.type.trim()) {
        errors.push(
          createError(
            "error",
            "MISSING_PARAM_TYPE",
            `Parameter "${param.name}" in method "${method.name}" has no type`,
            iface.id,
            "method",
            "parameters"
          )
        );
      }
    });
  });

  return errors;
}

// Validate enum completeness
function validateEnumCompleteness(enumDef: UmlEnumDef): UmlValidationError[] {
  const errors: UmlValidationError[] = [];

  if (enumDef.values.length === 0) {
    errors.push(
      createError(
        "warning",
        "EMPTY_ENUM",
        `Enum "${enumDef.name}" has no values`,
        enumDef.id,
        "enum"
      )
    );
  }

  if (!enumDef.description.trim()) {
    errors.push(
      createError(
        "info",
        "MISSING_DESCRIPTION",
        `Enum "${enumDef.name}" has no description`,
        enumDef.id,
        "enum",
        "description"
      )
    );
  }

  // Check for duplicate enum values
  const valueNames = new Set<string>();
  enumDef.values.forEach((val) => {
    if (valueNames.has(val.name)) {
      errors.push(
        createError(
          "error",
          "DUPLICATE_ENUM_VALUE",
          `Duplicate value "${val.name}" in enum "${enumDef.name}"`,
          enumDef.id,
          "enum",
          "values"
        )
      );
    }
    valueNames.add(val.name);
  });

  return errors;
}

// Validate struct completeness
function validateStructCompleteness(struct: UmlStructDef): UmlValidationError[] {
  const errors: UmlValidationError[] = [];

  if (struct.attributes.length === 0) {
    errors.push(
      createError(
        "warning",
        "EMPTY_STRUCT",
        `Struct "${struct.name}" has no fields`,
        struct.id,
        "struct"
      )
    );
  }

  if (!struct.description.trim()) {
    errors.push(
      createError(
        "info",
        "MISSING_DESCRIPTION",
        `Struct "${struct.name}" has no description`,
        struct.id,
        "struct",
        "description"
      )
    );
  }

  // Validate fields (attributes)
  struct.attributes.forEach((attr) => {
    if (!attr.type.trim()) {
      errors.push(
        createError(
          "error",
          "MISSING_TYPE",
          `Field "${attr.name}" in struct "${struct.name}" has no type`,
          struct.id,
          "attribute",
          "type"
        )
      );
    }
  });

  // Check for duplicate field names
  const fieldNames = new Set<string>();
  struct.attributes.forEach((attr) => {
    if (fieldNames.has(attr.name)) {
      errors.push(
        createError(
          "error",
          "DUPLICATE_FIELD",
          `Duplicate field "${attr.name}" in struct "${struct.name}"`,
          struct.id,
          "struct",
          "attributes"
        )
      );
    }
    fieldNames.add(attr.name);
  });

  return errors;
}

// Check if class implements all interface methods
function validateInterfaceImplementation(
  cls: UmlClassDef,
  ctx: ValidationContext
): UmlValidationError[] {
  const errors: UmlValidationError[] = [];

  cls.implements.forEach((ifaceName) => {
    const iface = ctx.interfaceMap.get(ifaceName);
    if (!iface) return; // Already reported as INVALID_IMPLEMENTS

    const classMethodNames = new Set(cls.methods.map((m) => m.name));

    iface.methods.forEach((ifaceMethod) => {
      if (!classMethodNames.has(ifaceMethod.name)) {
        errors.push(
          createError(
            "warning",
            "MISSING_IMPLEMENTATION",
            `Class "${cls.name}" does not implement method "${ifaceMethod.name}" from interface "${ifaceName}"`,
            cls.id,
            "class",
            "methods"
          )
        );
      }
    });
  });

  return errors;
}

// Main validation function
export function validateModule(module: UmlModuleDef): UmlValidationResult {
  const errors: UmlValidationError[] = [];
  const ctx = buildContext(module);

  // Global validations
  errors.push(...validateDuplicateNames(module));
  errors.push(...validateInheritanceCycles(ctx));

  // Per-entity validations
  module.classes.forEach((cls) => {
    errors.push(...validateClassReferences(cls, ctx));
    errors.push(...validateClassCompleteness(cls));
    errors.push(...validateInterfaceImplementation(cls, ctx));
  });

  module.interfaces.forEach((iface) => {
    errors.push(...validateInterfaceReferences(iface, ctx));
    errors.push(...validateInterfaceCompleteness(iface));
  });

  module.enums.forEach((enumDef) => {
    errors.push(...validateEnumCompleteness(enumDef));
  });

  module.structs.forEach((struct) => {
    errors.push(...validateStructCompleteness(struct));
  });

  // Calculate counts
  const errorCount = errors.filter((e) => e.severity === "error").length;
  const warningCount = errors.filter((e) => e.severity === "warning").length;
  const infoCount = errors.filter((e) => e.severity === "info").length;

  return {
    isValid: errorCount === 0,
    errors,
    errorCount,
    warningCount,
    infoCount,
  };
}

// Validate entire project
export function validateProject(project: UmlProjectDef): UmlValidationResult {
  const allErrors: UmlValidationError[] = [];

  project.modules.forEach((module) => {
    const result = validateModule(module);
    allErrors.push(...result.errors);
  });

  const errorCount = allErrors.filter((e) => e.severity === "error").length;
  const warningCount = allErrors.filter((e) => e.severity === "warning").length;
  const infoCount = allErrors.filter((e) => e.severity === "info").length;

  return {
    isValid: errorCount === 0,
    errors: allErrors,
    errorCount,
    warningCount,
    infoCount,
  };
}
