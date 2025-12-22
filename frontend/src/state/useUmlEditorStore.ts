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
} from "../api/types";

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
