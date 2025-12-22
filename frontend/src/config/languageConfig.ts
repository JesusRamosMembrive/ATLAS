/**
 * Language Configuration for UML Editor
 *
 * Defines which entities are available for each target language
 * and how they should be mapped when exporting/generating code.
 */

import type { UmlTargetLanguage } from "../api/types";

export type EntityType = "class" | "interface" | "enum" | "struct";

export interface LanguageEntityConfig {
  /** Whether this entity type is available in this language */
  available: boolean;
  /** Display name in the UI */
  displayName: string;
  /** How it maps to the target language (for hints/tooltips) */
  mapsTo: string;
}

export interface LanguageConfig {
  name: string;
  entities: Record<EntityType, LanguageEntityConfig>;
}

/**
 * Configuration for each supported language
 */
export const LANGUAGE_CONFIG: Record<UmlTargetLanguage, LanguageConfig> = {
  python: {
    name: "Python",
    entities: {
      class: {
        available: true,
        displayName: "Class",
        mapsTo: "class",
      },
      interface: {
        available: true,
        displayName: "Protocol",
        mapsTo: "Protocol (typing) or ABC",
      },
      enum: {
        available: true,
        displayName: "Enum",
        mapsTo: "enum.Enum",
      },
      struct: {
        available: true,
        displayName: "Dataclass",
        mapsTo: "@dataclass",
      },
    },
  },
  typescript: {
    name: "TypeScript",
    entities: {
      class: {
        available: true,
        displayName: "Class",
        mapsTo: "class",
      },
      interface: {
        available: true,
        displayName: "Interface",
        mapsTo: "interface",
      },
      enum: {
        available: true,
        displayName: "Enum",
        mapsTo: "enum",
      },
      struct: {
        available: true,
        displayName: "Type",
        mapsTo: "type or interface (data-only)",
      },
    },
  },
  cpp: {
    name: "C++",
    entities: {
      class: {
        available: true,
        displayName: "Class",
        mapsTo: "class",
      },
      interface: {
        available: true,
        displayName: "Abstract Class",
        mapsTo: "pure virtual class",
      },
      enum: {
        available: true,
        displayName: "Enum",
        mapsTo: "enum class",
      },
      struct: {
        available: true,
        displayName: "Struct",
        mapsTo: "struct",
      },
    },
  },
};

/**
 * Check if an entity type is available for a language
 */
export function isEntityAvailable(language: UmlTargetLanguage, entityType: EntityType): boolean {
  return LANGUAGE_CONFIG[language].entities[entityType].available;
}

/**
 * Get display name for an entity in a specific language
 */
export function getEntityDisplayName(language: UmlTargetLanguage, entityType: EntityType): string {
  return LANGUAGE_CONFIG[language].entities[entityType].displayName;
}

/**
 * Get what the entity maps to in the target language
 */
export function getEntityMapsTo(language: UmlTargetLanguage, entityType: EntityType): string {
  return LANGUAGE_CONFIG[language].entities[entityType].mapsTo;
}

/**
 * Check if changing from one language to another would cause entity compatibility issues
 * Returns a list of entity types that exist in the project but are not available in the new language
 */
export interface IncompatibleEntity {
  type: EntityType;
  count: number;
  currentName: string;
  newName: string;
}

export function getIncompatibleEntities(
  fromLanguage: UmlTargetLanguage,
  toLanguage: UmlTargetLanguage,
  entityCounts: Record<EntityType, number>
): IncompatibleEntity[] {
  const incompatible: IncompatibleEntity[] = [];

  for (const entityType of ["class", "interface", "enum", "struct"] as EntityType[]) {
    const count = entityCounts[entityType] || 0;
    if (count === 0) continue;

    const fromConfig = LANGUAGE_CONFIG[fromLanguage].entities[entityType];
    const toConfig = LANGUAGE_CONFIG[toLanguage].entities[entityType];

    // Check if the entity will be converted to something different
    if (fromConfig.displayName !== toConfig.displayName) {
      incompatible.push({
        type: entityType,
        count,
        currentName: fromConfig.displayName,
        newName: toConfig.displayName,
      });
    }
  }

  return incompatible;
}
