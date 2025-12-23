/**
 * UML Editor Store
 *
 * Manages the state for the UML Editor (AEGIS v2).
 * Uses Zustand for local state management.
 * Persists to localStorage with debounce for auto-save.
 */

import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

import type {
  UmlProjectDef,
  UmlModuleDef,
  UmlClassDef,
  UmlInterfaceDef,
  UmlEnumDef,
  UmlStructDef,
  UmlRelationshipDef,
  UmlMethodDef,
  UmlAttributeDef,
  UmlTargetLanguage,
  UmlInterfaceMethodDef,
} from "../api/types";
import type { DesignPatternTemplate } from "../config/designPatternTemplates";
import { calculatePositions, findEmptyArea, getTemplateBounds } from "../utils/templateLayoutEngine";

// Storage key for localStorage persistence
const STORAGE_KEY = "aegis-uml-editor-project";

// Helper to generate unique IDs
const generateId = () => crypto.randomUUID();

// Default empty hints
const defaultHints = () => ({
  edgeCases: [],
  performance: [],
  style: [],
  custom: [],
});

// Default empty method
const createDefaultMethod = (): UmlMethodDef => ({
  id: generateId(),
  name: "newMethod",
  visibility: "public",
  description: "",
  isStatic: false,
  isAsync: false,
  parameters: [],
  returnType: "void",
  returnDescription: "",
  preconditions: [],
  postconditions: [],
  throws: [],
  hints: defaultHints(),
  testCases: [],
});

// Default empty attribute
const createDefaultAttribute = (): UmlAttributeDef => ({
  id: generateId(),
  name: "newAttribute",
  type: "string",
  visibility: "private",
  description: "",
  defaultValue: null,
  isStatic: false,
  isReadonly: false,
});

// Default empty class
const createDefaultClass = (position: { x: number; y: number }): UmlClassDef => ({
  id: generateId(),
  name: "NewClass",
  description: "",
  isAbstract: false,
  extends: null,
  implements: [],
  attributes: [],
  methods: [],
  position,
});

// Default empty interface
const createDefaultInterface = (position: { x: number; y: number }): UmlInterfaceDef => ({
  id: generateId(),
  name: "INewInterface",
  description: "",
  extends: [],
  methods: [],
  position,
});

// Default empty enum
const createDefaultEnum = (position: { x: number; y: number }): UmlEnumDef => ({
  id: generateId(),
  name: "NewEnum",
  description: "",
  values: [],
  position,
});

// Default empty struct
const createDefaultStruct = (position: { x: number; y: number }): UmlStructDef => ({
  id: generateId(),
  name: "NewStruct",
  description: "",
  attributes: [],
  position,
});

// Default empty module
const createDefaultModule = (): UmlModuleDef => ({
  id: generateId(),
  name: "main",
  description: "",
  classes: [],
  interfaces: [],
  enums: [],
  structs: [],
  relationships: [],
});

// Default empty project
const createDefaultProject = (): UmlProjectDef => ({
  name: "New Project",
  version: "1.0.0",
  description: "",
  targetLanguage: "python",
  modules: [createDefaultModule()],
});

interface UmlEditorState {
  // Project state
  project: UmlProjectDef;
  currentModuleId: string | null;

  // Selection state
  selectedNodeId: string | null;
  selectedEdgeId: string | null;

  // UI state
  isDirty: boolean;

  // Project actions
  setProject: (project: UmlProjectDef) => void;
  resetProject: () => void;
  updateProjectMeta: (updates: Partial<Pick<UmlProjectDef, "name" | "version" | "description" | "targetLanguage">>) => void;

  // Module actions
  setCurrentModule: (moduleId: string) => void;
  addModule: (name: string) => void;
  updateModule: (moduleId: string, updates: Partial<UmlModuleDef>) => void;
  deleteModule: (moduleId: string) => void;

  // Class actions
  addClass: (position: { x: number; y: number }) => string;
  updateClass: (classId: string, updates: Partial<UmlClassDef>) => void;
  deleteClass: (classId: string) => void;
  updateClassPosition: (classId: string, position: { x: number; y: number }) => void;

  // Interface actions
  addInterface: (position: { x: number; y: number }) => string;
  updateInterface: (interfaceId: string, updates: Partial<UmlInterfaceDef>) => void;
  deleteInterface: (interfaceId: string) => void;
  updateInterfacePosition: (interfaceId: string, position: { x: number; y: number }) => void;

  // Enum actions
  addEnum: (position: { x: number; y: number }) => string;
  updateEnum: (enumId: string, updates: Partial<UmlEnumDef>) => void;
  deleteEnum: (enumId: string) => void;
  updateEnumPosition: (enumId: string, position: { x: number; y: number }) => void;

  // Struct actions
  addStruct: (position: { x: number; y: number }) => string;
  updateStruct: (structId: string, updates: Partial<UmlStructDef>) => void;
  deleteStruct: (structId: string) => void;
  updateStructPosition: (structId: string, position: { x: number; y: number }) => void;

  // Struct attribute actions
  addStructAttribute: (structId: string) => string;
  updateStructAttribute: (structId: string, attributeId: string, updates: Partial<UmlAttributeDef>) => void;
  deleteStructAttribute: (structId: string, attributeId: string) => void;

  // Method actions (on class)
  addMethod: (classId: string) => string;
  updateMethod: (classId: string, methodId: string, updates: Partial<UmlMethodDef>) => void;
  deleteMethod: (classId: string, methodId: string) => void;

  // Attribute actions (on class)
  addAttribute: (classId: string) => string;
  updateAttribute: (classId: string, attributeId: string, updates: Partial<UmlAttributeDef>) => void;
  deleteAttribute: (classId: string, attributeId: string) => void;

  // Relationship actions
  addRelationship: (relationship: Omit<UmlRelationshipDef, "id">) => string;
  updateRelationship: (relationshipId: string, updates: Partial<UmlRelationshipDef>) => void;
  deleteRelationship: (relationshipId: string) => void;

  // Selection actions
  selectNode: (nodeId: string | null) => void;
  selectEdge: (edgeId: string | null) => void;
  clearSelection: () => void;

  // Helpers
  getCurrentModule: () => UmlModuleDef | null;
  getClassById: (classId: string) => UmlClassDef | null;
  getInterfaceById: (interfaceId: string) => UmlInterfaceDef | null;
  getEnumById: (enumId: string) => UmlEnumDef | null;
  getStructById: (structId: string) => UmlStructDef | null;
  getRelationshipById: (relationshipId: string) => UmlRelationshipDef | null;
  getSelectedEntity: () => UmlClassDef | UmlInterfaceDef | UmlEnumDef | UmlStructDef | null;
  getAllTypeNames: () => string[];
  setSelectedNode: (nodeId: string) => void;

  // Template actions
  applyTemplate: (template: DesignPatternTemplate) => string[];

  // Merge actions (for AI generation)
  mergeProject: (project: UmlProjectDef) => void;

  // Component view state (for connected component filtering)
  activeComponentId: string | null;
  setActiveComponentId: (componentId: string | null) => void;

  // Layout actions
  updateEntityPosition: (entityId: string, position: { x: number; y: number }) => void;
  batchUpdatePositions: (positions: Map<string, { x: number; y: number }>) => void;
}

export const useUmlEditorStore = create<UmlEditorState>()(
  devtools(
    persist(
      (set, get) => {
        const defaultProject = createDefaultProject();

      return {
        // Initial state
        project: defaultProject,
        currentModuleId: defaultProject.modules[0]?.id ?? null,
        selectedNodeId: null,
        selectedEdgeId: null,
        isDirty: false,
        activeComponentId: null,

        // Project actions
        setProject: (project) =>
          set({
            project,
            currentModuleId: project.modules[0]?.id ?? null,
            selectedNodeId: null,
            selectedEdgeId: null,
            isDirty: false,
          }),

        resetProject: () => {
          const newProject = createDefaultProject();
          set({
            project: newProject,
            currentModuleId: newProject.modules[0]?.id ?? null,
            selectedNodeId: null,
            selectedEdgeId: null,
            isDirty: false,
          });
        },

        updateProjectMeta: (updates) =>
          set((state) => ({
            project: { ...state.project, ...updates },
            isDirty: true,
          })),

        // Module actions
        setCurrentModule: (moduleId) =>
          set({ currentModuleId: moduleId, selectedNodeId: null, selectedEdgeId: null }),

        addModule: (name) =>
          set((state) => {
            const newModule = { ...createDefaultModule(), name };
            return {
              project: {
                ...state.project,
                modules: [...state.project.modules, newModule],
              },
              currentModuleId: newModule.id,
              isDirty: true,
            };
          }),

        updateModule: (moduleId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) =>
                m.id === moduleId ? { ...m, ...updates } : m
              ),
            },
            isDirty: true,
          })),

        deleteModule: (moduleId) =>
          set((state) => {
            const newModules = state.project.modules.filter((m) => m.id !== moduleId);
            return {
              project: { ...state.project, modules: newModules },
              currentModuleId: newModules[0]?.id ?? null,
              isDirty: true,
            };
          }),

        // Class actions
        addClass: (position) => {
          const newClass = createDefaultClass(position);
          set((state) => {
            const moduleId = state.currentModuleId;
            if (!moduleId) return state;

            return {
              project: {
                ...state.project,
                modules: state.project.modules.map((m) =>
                  m.id === moduleId
                    ? { ...m, classes: [...m.classes, newClass] }
                    : m
                ),
              },
              selectedNodeId: newClass.id,
              isDirty: true,
            };
          });
          return newClass.id;
        },

        updateClass: (classId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === classId ? { ...c, ...updates } : c
                ),
              })),
            },
            isDirty: true,
          })),

        deleteClass: (classId) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.filter((c) => c.id !== classId),
                relationships: m.relationships.filter(
                  (r) => r.from !== classId && r.to !== classId
                ),
              })),
            },
            selectedNodeId: state.selectedNodeId === classId ? null : state.selectedNodeId,
            isDirty: true,
          })),

        updateClassPosition: (classId, position) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === classId ? { ...c, position } : c
                ),
              })),
            },
          })),

        // Interface actions
        addInterface: (position) => {
          const newInterface = createDefaultInterface(position);
          set((state) => {
            const moduleId = state.currentModuleId;
            if (!moduleId) return state;

            return {
              project: {
                ...state.project,
                modules: state.project.modules.map((m) =>
                  m.id === moduleId
                    ? { ...m, interfaces: [...m.interfaces, newInterface] }
                    : m
                ),
              },
              selectedNodeId: newInterface.id,
              isDirty: true,
            };
          });
          return newInterface.id;
        },

        updateInterface: (interfaceId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                interfaces: m.interfaces.map((i) =>
                  i.id === interfaceId ? { ...i, ...updates } : i
                ),
              })),
            },
            isDirty: true,
          })),

        deleteInterface: (interfaceId) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                interfaces: m.interfaces.filter((i) => i.id !== interfaceId),
                relationships: m.relationships.filter(
                  (r) => r.from !== interfaceId && r.to !== interfaceId
                ),
              })),
            },
            selectedNodeId: state.selectedNodeId === interfaceId ? null : state.selectedNodeId,
            isDirty: true,
          })),

        updateInterfacePosition: (interfaceId, position) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                interfaces: m.interfaces.map((i) =>
                  i.id === interfaceId ? { ...i, position } : i
                ),
              })),
            },
          })),

        // Enum actions
        addEnum: (position) => {
          const newEnum = createDefaultEnum(position);
          set((state) => {
            const moduleId = state.currentModuleId;
            if (!moduleId) return state;

            return {
              project: {
                ...state.project,
                modules: state.project.modules.map((m) =>
                  m.id === moduleId
                    ? { ...m, enums: [...m.enums, newEnum] }
                    : m
                ),
              },
              selectedNodeId: newEnum.id,
              isDirty: true,
            };
          });
          return newEnum.id;
        },

        updateEnum: (enumId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                enums: m.enums.map((e) =>
                  e.id === enumId ? { ...e, ...updates } : e
                ),
              })),
            },
            isDirty: true,
          })),

        deleteEnum: (enumId) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                enums: m.enums.filter((e) => e.id !== enumId),
              })),
            },
            selectedNodeId: state.selectedNodeId === enumId ? null : state.selectedNodeId,
            isDirty: true,
          })),

        updateEnumPosition: (enumId, position) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                enums: m.enums.map((e) =>
                  e.id === enumId ? { ...e, position } : e
                ),
              })),
            },
          })),

        // Struct actions
        addStruct: (position) => {
          const newStruct = createDefaultStruct(position);
          set((state) => {
            const moduleId = state.currentModuleId;
            if (!moduleId) return state;

            return {
              project: {
                ...state.project,
                modules: state.project.modules.map((m) =>
                  m.id === moduleId
                    ? { ...m, structs: [...m.structs, newStruct] }
                    : m
                ),
              },
              selectedNodeId: newStruct.id,
              isDirty: true,
            };
          });
          return newStruct.id;
        },

        updateStruct: (structId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                structs: m.structs.map((s) =>
                  s.id === structId ? { ...s, ...updates } : s
                ),
              })),
            },
            isDirty: true,
          })),

        deleteStruct: (structId) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                structs: m.structs.filter((s) => s.id !== structId),
              })),
            },
            selectedNodeId: state.selectedNodeId === structId ? null : state.selectedNodeId,
            isDirty: true,
          })),

        updateStructPosition: (structId, position) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                structs: m.structs.map((s) =>
                  s.id === structId ? { ...s, position } : s
                ),
              })),
            },
          })),

        // Struct attribute actions
        addStructAttribute: (structId) => {
          const newAttribute = createDefaultAttribute();
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                structs: m.structs.map((s) =>
                  s.id === structId
                    ? { ...s, attributes: [...s.attributes, newAttribute] }
                    : s
                ),
              })),
            },
            isDirty: true,
          }));
          return newAttribute.id;
        },

        updateStructAttribute: (structId, attributeId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                structs: m.structs.map((s) =>
                  s.id === structId
                    ? {
                        ...s,
                        attributes: s.attributes.map((a) =>
                          a.id === attributeId ? { ...a, ...updates } : a
                        ),
                      }
                    : s
                ),
              })),
            },
            isDirty: true,
          })),

        deleteStructAttribute: (structId, attributeId) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                structs: m.structs.map((s) =>
                  s.id === structId
                    ? { ...s, attributes: s.attributes.filter((a) => a.id !== attributeId) }
                    : s
                ),
              })),
            },
            isDirty: true,
          })),

        // Method actions
        addMethod: (classId) => {
          const newMethod = createDefaultMethod();
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === classId
                    ? { ...c, methods: [...c.methods, newMethod] }
                    : c
                ),
              })),
            },
            isDirty: true,
          }));
          return newMethod.id;
        },

        updateMethod: (classId, methodId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === classId
                    ? {
                        ...c,
                        methods: c.methods.map((method) =>
                          method.id === methodId ? { ...method, ...updates } : method
                        ),
                      }
                    : c
                ),
              })),
            },
            isDirty: true,
          })),

        deleteMethod: (classId, methodId) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === classId
                    ? { ...c, methods: c.methods.filter((method) => method.id !== methodId) }
                    : c
                ),
              })),
            },
            isDirty: true,
          })),

        // Attribute actions
        addAttribute: (classId) => {
          const newAttribute = createDefaultAttribute();
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === classId
                    ? { ...c, attributes: [...c.attributes, newAttribute] }
                    : c
                ),
              })),
            },
            isDirty: true,
          }));
          return newAttribute.id;
        },

        updateAttribute: (classId, attributeId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === classId
                    ? {
                        ...c,
                        attributes: c.attributes.map((attr) =>
                          attr.id === attributeId ? { ...attr, ...updates } : attr
                        ),
                      }
                    : c
                ),
              })),
            },
            isDirty: true,
          })),

        deleteAttribute: (classId, attributeId) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === classId
                    ? { ...c, attributes: c.attributes.filter((attr) => attr.id !== attributeId) }
                    : c
                ),
              })),
            },
            isDirty: true,
          })),

        // Relationship actions
        addRelationship: (relationship) => {
          const newRelationship: UmlRelationshipDef = {
            ...relationship,
            id: generateId(),
          };
          set((state) => {
            const moduleId = state.currentModuleId;
            if (!moduleId) return state;

            return {
              project: {
                ...state.project,
                modules: state.project.modules.map((m) =>
                  m.id === moduleId
                    ? { ...m, relationships: [...m.relationships, newRelationship] }
                    : m
                ),
              },
              isDirty: true,
            };
          });
          return newRelationship.id;
        },

        updateRelationship: (relationshipId, updates) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                relationships: m.relationships.map((r) =>
                  r.id === relationshipId ? { ...r, ...updates } : r
                ),
              })),
            },
            isDirty: true,
          })),

        deleteRelationship: (relationshipId) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                relationships: m.relationships.filter((r) => r.id !== relationshipId),
              })),
            },
            selectedEdgeId: state.selectedEdgeId === relationshipId ? null : state.selectedEdgeId,
            isDirty: true,
          })),

        // Selection actions
        selectNode: (nodeId) =>
          set({ selectedNodeId: nodeId, selectedEdgeId: null }),

        selectEdge: (edgeId) =>
          set({ selectedEdgeId: edgeId, selectedNodeId: null }),

        clearSelection: () =>
          set({ selectedNodeId: null, selectedEdgeId: null }),

        // Helpers
        getCurrentModule: () => {
          const state = get();
          if (!state.currentModuleId) return null;
          return state.project.modules.find((m) => m.id === state.currentModuleId) ?? null;
        },

        getClassById: (classId) => {
          const state = get();
          for (const module of state.project.modules) {
            const cls = module.classes.find((c) => c.id === classId);
            if (cls) return cls;
          }
          return null;
        },

        getInterfaceById: (interfaceId) => {
          const state = get();
          for (const module of state.project.modules) {
            const iface = module.interfaces.find((i) => i.id === interfaceId);
            if (iface) return iface;
          }
          return null;
        },

        getEnumById: (enumId) => {
          const state = get();
          for (const module of state.project.modules) {
            const enm = module.enums.find((e) => e.id === enumId);
            if (enm) return enm;
          }
          return null;
        },

        getStructById: (structId) => {
          const state = get();
          for (const module of state.project.modules) {
            const struct = module.structs.find((s) => s.id === structId);
            if (struct) return struct;
          }
          return null;
        },

        getRelationshipById: (relationshipId) => {
          const state = get();
          for (const module of state.project.modules) {
            const rel = module.relationships.find((r) => r.id === relationshipId);
            if (rel) return rel;
          }
          return null;
        },

        getSelectedEntity: () => {
          const state = get();
          if (!state.selectedNodeId) return null;

          return (
            state.getClassById(state.selectedNodeId) ??
            state.getInterfaceById(state.selectedNodeId) ??
            state.getEnumById(state.selectedNodeId) ??
            state.getStructById(state.selectedNodeId)
          );
        },

        getAllTypeNames: () => {
          const state = get();
          const types: string[] = [];

          for (const module of state.project.modules) {
            types.push(...module.classes.map((c) => c.name));
            types.push(...module.interfaces.map((i) => i.name));
            types.push(...module.enums.map((e) => e.name));
            types.push(...module.structs.map((s) => s.name));
          }

          return types;
        },

        setSelectedNode: (nodeId) =>
          set({ selectedNodeId: nodeId, selectedEdgeId: null }),

        // Template actions
        applyTemplate: (template) => {
          const state = get();
          const moduleId = state.currentModuleId;
          if (!moduleId) return [];

          const module = state.project.modules.find((m) => m.id === moduleId);
          if (!module) return [];

          // Collect existing positions to avoid overlaps
          const existingPositions = [
            ...module.classes.map((c) => c.position),
            ...module.interfaces.map((i) => i.position),
            ...module.enums.map((e) => e.position),
            ...module.structs.map((s) => s.position),
          ];

          // Calculate start position for the template
          const templateBounds = getTemplateBounds(template.layoutHints);
          const startPos = findEmptyArea(existingPositions, templateBounds);

          // Calculate positions for each entity
          const positions = calculatePositions(template.layoutHints, {
            startX: startPos.x,
            startY: startPos.y,
          });

          // Map template keys to generated IDs
          const keyToId = new Map<string, string>();

          // Create new classes and interfaces
          const newClasses: UmlClassDef[] = [];
          const newInterfaces: UmlInterfaceDef[] = [];

          for (const entity of template.entities) {
            const id = generateId();
            keyToId.set(entity.key, id);
            const position = positions.get(entity.key) ?? { x: 100, y: 100 };

            if (entity.type === "class") {
              newClasses.push({
                id,
                name: entity.name,
                description: entity.description ?? "",
                isAbstract: entity.isAbstract,
                extends: null,
                implements: [],
                attributes: entity.attributes.map((a) => ({
                  id: generateId(),
                  name: a.name,
                  type: a.type,
                  visibility: a.visibility,
                  description: "",
                  defaultValue: null,
                  isStatic: a.isStatic ?? false,
                  isReadonly: false,
                })),
                methods: entity.methods.map((m) => ({
                  id: generateId(),
                  name: m.name,
                  visibility: m.visibility ?? "public",
                  description: m.description ?? "",
                  isStatic: m.isStatic ?? false,
                  isAsync: false,
                  isAbstract: m.isAbstract ?? false,
                  parameters: (m.parameters ?? []).map((p) => ({
                    name: p.name,
                    type: p.type,
                    description: "",
                    isOptional: false,
                    defaultValue: null,
                  })),
                  returnType: m.returnType,
                  returnDescription: "",
                  preconditions: [],
                  postconditions: [],
                  throws: [],
                  hints: defaultHints(),
                  testCases: [],
                })),
                position,
              });
            } else if (entity.type === "interface") {
              const interfaceMethods: UmlInterfaceMethodDef[] = entity.methods.map((m) => ({
                id: generateId(),
                name: m.name,
                description: m.description ?? "",
                parameters: (m.parameters ?? []).map((p) => ({
                  name: p.name,
                  type: p.type,
                  description: "",
                  isOptional: false,
                  defaultValue: null,
                })),
                returnType: m.returnType,
              }));

              newInterfaces.push({
                id,
                name: entity.name,
                description: entity.description ?? "",
                extends: [],
                methods: interfaceMethods,
                position,
              });
            }
          }

          // Create relationships with mapped IDs
          const newRelationships: UmlRelationshipDef[] = template.relationships.map((r) => ({
            id: generateId(),
            type: r.type,
            from: keyToId.get(r.from) ?? "",
            to: keyToId.get(r.to) ?? "",
            description: r.description ?? "",
            cardinality: r.cardinality ?? null,
          }));

          // Apply changes in a single state update
          set((currentState) => ({
            project: {
              ...currentState.project,
              modules: currentState.project.modules.map((m) =>
                m.id === moduleId
                  ? {
                      ...m,
                      classes: [...m.classes, ...newClasses],
                      interfaces: [...m.interfaces, ...newInterfaces],
                      relationships: [...m.relationships, ...newRelationships],
                    }
                  : m
              ),
            },
            isDirty: true,
          }));

          return Array.from(keyToId.values());
        },

        // Merge actions - add entities from another project without replacing
        mergeProject: (importedProject) => {
          const state = get();
          const moduleId = state.currentModuleId;
          if (!moduleId) return;

          const currentModule = state.project.modules.find((m) => m.id === moduleId);
          if (!currentModule) return;

          // Get imported module (use first module from imported project)
          const importedModule = importedProject.modules[0];
          if (!importedModule) return;

          // Collect existing positions to find empty area
          const existingPositions = [
            ...currentModule.classes.map((c) => c.position),
            ...currentModule.interfaces.map((i) => i.position),
            ...currentModule.enums.map((e) => e.position),
            ...currentModule.structs.map((s) => s.position),
          ];

          // Calculate offset for imported entities
          const startPos = findEmptyArea(existingPositions, { rows: 3, cols: 3 });

          // Map old IDs to new IDs for relationships
          const idMap = new Map<string, string>();

          // Process classes - generate new IDs and offset positions
          const newClasses: UmlClassDef[] = importedModule.classes.map((cls) => {
            const newId = generateId();
            idMap.set(cls.id, newId);
            return {
              ...cls,
              id: newId,
              position: {
                x: startPos.x + (cls.position?.x ?? 0),
                y: startPos.y + (cls.position?.y ?? 0),
              },
              attributes: cls.attributes.map((a) => ({ ...a, id: generateId() })),
              methods: cls.methods.map((m) => ({ ...m, id: generateId() })),
            };
          });

          // Process interfaces
          const newInterfaces: UmlInterfaceDef[] = importedModule.interfaces.map((iface) => {
            const newId = generateId();
            idMap.set(iface.id, newId);
            return {
              ...iface,
              id: newId,
              position: {
                x: startPos.x + (iface.position?.x ?? 0),
                y: startPos.y + (iface.position?.y ?? 0),
              },
              methods: iface.methods.map((m) => ({ ...m, id: generateId() })),
            };
          });

          // Process enums
          const newEnums: UmlEnumDef[] = importedModule.enums.map((enm) => {
            const newId = generateId();
            idMap.set(enm.id, newId);
            return {
              ...enm,
              id: newId,
              position: {
                x: startPos.x + (enm.position?.x ?? 0),
                y: startPos.y + (enm.position?.y ?? 0),
              },
            };
          });

          // Process structs
          const newStructs: UmlStructDef[] = importedModule.structs.map((struct) => {
            const newId = generateId();
            idMap.set(struct.id, newId);
            return {
              ...struct,
              id: newId,
              position: {
                x: startPos.x + (struct.position?.x ?? 0),
                y: startPos.y + (struct.position?.y ?? 0),
              },
              attributes: struct.attributes.map((a) => ({ ...a, id: generateId() })),
            };
          });

          // Process relationships - remap IDs
          const newRelationships: UmlRelationshipDef[] = importedModule.relationships.map((rel) => ({
            ...rel,
            id: generateId(),
            from: idMap.get(rel.from) ?? rel.from,
            to: idMap.get(rel.to) ?? rel.to,
          }));

          // Apply the merge
          set((currentState) => ({
            project: {
              ...currentState.project,
              modules: currentState.project.modules.map((m) =>
                m.id === moduleId
                  ? {
                      ...m,
                      classes: [...m.classes, ...newClasses],
                      interfaces: [...m.interfaces, ...newInterfaces],
                      enums: [...m.enums, ...newEnums],
                      structs: [...m.structs, ...newStructs],
                      relationships: [...m.relationships, ...newRelationships],
                    }
                  : m
              ),
            },
            isDirty: true,
          }));
        },

        // Component filtering actions
        setActiveComponentId: (componentId) =>
          set({ activeComponentId: componentId }),

        // Layout actions - update single entity position
        updateEntityPosition: (entityId, position) =>
          set((state) => ({
            project: {
              ...state.project,
              modules: state.project.modules.map((m) => ({
                ...m,
                classes: m.classes.map((c) =>
                  c.id === entityId ? { ...c, position } : c
                ),
                interfaces: m.interfaces.map((i) =>
                  i.id === entityId ? { ...i, position } : i
                ),
                enums: m.enums.map((e) =>
                  e.id === entityId ? { ...e, position } : e
                ),
                structs: m.structs.map((s) =>
                  s.id === entityId ? { ...s, position } : s
                ),
              })),
            },
          })),

        // Layout actions - batch update multiple positions (for auto-layout)
        batchUpdatePositions: (positions) =>
          set((state) => {
            // positions is always a Map from the interface
            const positionMap = positions;
            return {
              project: {
                ...state.project,
                modules: state.project.modules.map((m) => ({
                  ...m,
                  classes: m.classes.map((c) => {
                    const newPos = positionMap.get(c.id);
                    return newPos ? { ...c, position: { x: newPos.x, y: newPos.y } } : c;
                  }),
                  interfaces: m.interfaces.map((i) => {
                    const newPos = positionMap.get(i.id);
                    return newPos ? { ...i, position: { x: newPos.x, y: newPos.y } } : i;
                  }),
                  enums: m.enums.map((e) => {
                    const newPos = positionMap.get(e.id);
                    return newPos ? { ...e, position: { x: newPos.x, y: newPos.y } } : e;
                  }),
                  structs: m.structs.map((s) => {
                    const newPos = positionMap.get(s.id);
                    return newPos ? { ...s, position: { x: newPos.x, y: newPos.y } } : s;
                  }),
                })),
              },
            };
          }),
      };
      },
      {
        name: STORAGE_KEY,
        // Only persist project data, not UI state
        partialize: (state) => ({
          project: state.project,
          currentModuleId: state.currentModuleId,
        }),
        // Merge persisted state with default state
        merge: (persistedState, currentState) => {
          const persisted = persistedState as Partial<UmlEditorState> | undefined;
          if (!persisted?.project) {
            return currentState;
          }
          return {
            ...currentState,
            project: persisted.project,
            currentModuleId: persisted.currentModuleId ?? persisted.project.modules[0]?.id ?? null,
            isDirty: false,
          };
        },
      }
    ),
    { name: "uml-editor-store" }
  )
);
