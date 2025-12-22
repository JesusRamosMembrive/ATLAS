/**
 * Design Pattern Templates - GoF Pattern Definitions
 *
 * Contains type definitions and template data for all 23 Gang of Four design patterns.
 * Used by the TemplatesDialog to insert pre-configured pattern structures.
 */

import type { UmlTargetLanguage, UmlVisibility, UmlRelationType } from "../api/types";

// =============================================================================
// Type Definitions
// =============================================================================

export type PatternCategory = "creational" | "structural" | "behavioral";

export interface PatternCategoryInfo {
  id: PatternCategory;
  name: string;
  description: string;
  icon: string;
}

export interface TemplateParameter {
  name: string;
  type: string;
}

export interface TemplateMethod {
  name: string;
  returnType: string;
  visibility?: UmlVisibility;
  isAbstract?: boolean;
  isStatic?: boolean;
  parameters?: TemplateParameter[];
  description?: string;
}

export interface TemplateAttribute {
  name: string;
  type: string;
  visibility: UmlVisibility;
  isStatic?: boolean;
}

interface TemplateEntityBase {
  key: string;
  name: string;
  description?: string;
}

export interface TemplateClass extends TemplateEntityBase {
  type: "class";
  isAbstract: boolean;
  attributes: TemplateAttribute[];
  methods: TemplateMethod[];
}

export interface TemplateInterface extends TemplateEntityBase {
  type: "interface";
  methods: TemplateMethod[];
}

export type TemplateEntity = TemplateClass | TemplateInterface;

export interface TemplateRelationship {
  from: string;
  to: string;
  type: UmlRelationType;
  description?: string;
  cardinality?: string;
}

export interface TemplateLayoutHint {
  key: string;
  row: number;
  col: number;
}

export interface DesignPatternTemplate {
  id: string;
  name: string;
  category: PatternCategory;
  description: string;
  reference?: string;
  languageNames?: Partial<Record<UmlTargetLanguage, Record<string, string>>>;
  entities: TemplateEntity[];
  relationships: TemplateRelationship[];
  layoutHints: TemplateLayoutHint[];
}

// =============================================================================
// Category Definitions
// =============================================================================

export const PATTERN_CATEGORIES: PatternCategoryInfo[] = [
  {
    id: "creational",
    name: "Creational",
    description: "Object creation mechanisms",
    icon: "+",
  },
  {
    id: "structural",
    name: "Structural",
    description: "Object composition",
    icon: "[]",
  },
  {
    id: "behavioral",
    name: "Behavioral",
    description: "Object interaction",
    icon: "->",
  },
];

// =============================================================================
// CREATIONAL PATTERNS (5)
// =============================================================================

const FACTORY_METHOD: DesignPatternTemplate = {
  id: "factory-method",
  name: "Factory Method",
  category: "creational",
  description: "Define an interface for creating an object, but let subclasses decide which class to instantiate.",
  reference: "GoF - Creational",
  entities: [
    {
      key: "product",
      type: "interface",
      name: "IProduct",
      description: "Interface for products created by the factory",
      methods: [{ name: "operation", returnType: "void" }],
    },
    {
      key: "concrete_product_a",
      type: "class",
      name: "ConcreteProductA",
      description: "Concrete implementation of Product",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operation", returnType: "void", visibility: "public" }],
    },
    {
      key: "concrete_product_b",
      type: "class",
      name: "ConcreteProductB",
      description: "Another concrete implementation",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operation", returnType: "void", visibility: "public" }],
    },
    {
      key: "creator",
      type: "class",
      name: "Creator",
      description: "Abstract creator with factory method",
      isAbstract: true,
      attributes: [],
      methods: [
        { name: "factoryMethod", returnType: "IProduct", visibility: "public", isAbstract: true },
        { name: "someOperation", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "concrete_creator_a",
      type: "class",
      name: "ConcreteCreatorA",
      description: "Creates ConcreteProductA",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "factoryMethod", returnType: "IProduct", visibility: "public" }],
    },
    {
      key: "concrete_creator_b",
      type: "class",
      name: "ConcreteCreatorB",
      description: "Creates ConcreteProductB",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "factoryMethod", returnType: "IProduct", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "concrete_product_a", to: "product", type: "implementation" },
    { from: "concrete_product_b", to: "product", type: "implementation" },
    { from: "concrete_creator_a", to: "creator", type: "inheritance" },
    { from: "concrete_creator_b", to: "creator", type: "inheritance" },
    { from: "creator", to: "product", type: "dependency", description: "creates" },
  ],
  layoutHints: [
    { key: "product", row: 0, col: 1 },
    { key: "concrete_product_a", row: 1, col: 0 },
    { key: "concrete_product_b", row: 1, col: 2 },
    { key: "creator", row: 2, col: 1 },
    { key: "concrete_creator_a", row: 3, col: 0 },
    { key: "concrete_creator_b", row: 3, col: 2 },
  ],
};

const ABSTRACT_FACTORY: DesignPatternTemplate = {
  id: "abstract-factory",
  name: "Abstract Factory",
  category: "creational",
  description: "Provide an interface for creating families of related objects without specifying their concrete classes.",
  reference: "GoF - Creational",
  entities: [
    {
      key: "abstract_factory",
      type: "interface",
      name: "IAbstractFactory",
      description: "Interface for creating abstract products",
      methods: [
        { name: "createProductA", returnType: "IProductA" },
        { name: "createProductB", returnType: "IProductB" },
      ],
    },
    {
      key: "concrete_factory_1",
      type: "class",
      name: "ConcreteFactory1",
      description: "Creates family 1 products",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "createProductA", returnType: "IProductA", visibility: "public" },
        { name: "createProductB", returnType: "IProductB", visibility: "public" },
      ],
    },
    {
      key: "concrete_factory_2",
      type: "class",
      name: "ConcreteFactory2",
      description: "Creates family 2 products",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "createProductA", returnType: "IProductA", visibility: "public" },
        { name: "createProductB", returnType: "IProductB", visibility: "public" },
      ],
    },
    {
      key: "product_a",
      type: "interface",
      name: "IProductA",
      description: "Abstract product A",
      methods: [{ name: "operationA", returnType: "void" }],
    },
    {
      key: "product_b",
      type: "interface",
      name: "IProductB",
      description: "Abstract product B",
      methods: [{ name: "operationB", returnType: "void" }],
    },
    {
      key: "product_a1",
      type: "class",
      name: "ProductA1",
      description: "Product A variant 1",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationA", returnType: "void", visibility: "public" }],
    },
    {
      key: "product_a2",
      type: "class",
      name: "ProductA2",
      description: "Product A variant 2",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationA", returnType: "void", visibility: "public" }],
    },
    {
      key: "product_b1",
      type: "class",
      name: "ProductB1",
      description: "Product B variant 1",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationB", returnType: "void", visibility: "public" }],
    },
    {
      key: "product_b2",
      type: "class",
      name: "ProductB2",
      description: "Product B variant 2",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationB", returnType: "void", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "concrete_factory_1", to: "abstract_factory", type: "implementation" },
    { from: "concrete_factory_2", to: "abstract_factory", type: "implementation" },
    { from: "product_a1", to: "product_a", type: "implementation" },
    { from: "product_a2", to: "product_a", type: "implementation" },
    { from: "product_b1", to: "product_b", type: "implementation" },
    { from: "product_b2", to: "product_b", type: "implementation" },
    { from: "concrete_factory_1", to: "product_a1", type: "dependency", description: "creates" },
    { from: "concrete_factory_1", to: "product_b1", type: "dependency", description: "creates" },
    { from: "concrete_factory_2", to: "product_a2", type: "dependency", description: "creates" },
    { from: "concrete_factory_2", to: "product_b2", type: "dependency", description: "creates" },
  ],
  layoutHints: [
    { key: "abstract_factory", row: 0, col: 0 },
    { key: "concrete_factory_1", row: 1, col: 0 },
    { key: "concrete_factory_2", row: 2, col: 0 },
    { key: "product_a", row: 0, col: 2 },
    { key: "product_b", row: 0, col: 3 },
    { key: "product_a1", row: 1, col: 2 },
    { key: "product_b1", row: 1, col: 3 },
    { key: "product_a2", row: 2, col: 2 },
    { key: "product_b2", row: 2, col: 3 },
  ],
};

const BUILDER: DesignPatternTemplate = {
  id: "builder",
  name: "Builder",
  category: "creational",
  description: "Separate the construction of a complex object from its representation.",
  reference: "GoF - Creational",
  entities: [
    {
      key: "builder",
      type: "interface",
      name: "IBuilder",
      description: "Interface for building parts of a product",
      methods: [
        { name: "reset", returnType: "void" },
        { name: "buildPartA", returnType: "void" },
        { name: "buildPartB", returnType: "void" },
        { name: "buildPartC", returnType: "void" },
      ],
    },
    {
      key: "concrete_builder",
      type: "class",
      name: "ConcreteBuilder",
      description: "Builds and assembles parts of the product",
      isAbstract: false,
      attributes: [{ name: "product", type: "Product", visibility: "private" }],
      methods: [
        { name: "reset", returnType: "void", visibility: "public" },
        { name: "buildPartA", returnType: "void", visibility: "public" },
        { name: "buildPartB", returnType: "void", visibility: "public" },
        { name: "buildPartC", returnType: "void", visibility: "public" },
        { name: "getResult", returnType: "Product", visibility: "public" },
      ],
    },
    {
      key: "product",
      type: "class",
      name: "Product",
      description: "The complex object being built",
      isAbstract: false,
      attributes: [
        { name: "partA", type: "string", visibility: "public" },
        { name: "partB", type: "string", visibility: "public" },
        { name: "partC", type: "string", visibility: "public" },
      ],
      methods: [],
    },
    {
      key: "director",
      type: "class",
      name: "Director",
      description: "Defines the order of building steps",
      isAbstract: false,
      attributes: [{ name: "builder", type: "IBuilder", visibility: "private" }],
      methods: [
        { name: "setBuilder", returnType: "void", visibility: "public", parameters: [{ name: "builder", type: "IBuilder" }] },
        { name: "buildMinimalProduct", returnType: "void", visibility: "public" },
        { name: "buildFullProduct", returnType: "void", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_builder", to: "builder", type: "implementation" },
    { from: "concrete_builder", to: "product", type: "dependency", description: "creates" },
    { from: "director", to: "builder", type: "aggregation", description: "uses" },
  ],
  layoutHints: [
    { key: "director", row: 0, col: 0 },
    { key: "builder", row: 0, col: 1 },
    { key: "concrete_builder", row: 1, col: 1 },
    { key: "product", row: 1, col: 2 },
  ],
};

const PROTOTYPE: DesignPatternTemplate = {
  id: "prototype",
  name: "Prototype",
  category: "creational",
  description: "Specify the kinds of objects to create using a prototypical instance, and create new objects by copying this prototype.",
  reference: "GoF - Creational",
  entities: [
    {
      key: "prototype",
      type: "interface",
      name: "IPrototype",
      description: "Interface declaring the cloning method",
      methods: [{ name: "clone", returnType: "IPrototype" }],
    },
    {
      key: "concrete_prototype_a",
      type: "class",
      name: "ConcretePrototypeA",
      description: "Implements cloning for type A",
      isAbstract: false,
      attributes: [{ name: "fieldA", type: "string", visibility: "private" }],
      methods: [
        { name: "clone", returnType: "IPrototype", visibility: "public" },
        { name: "getFieldA", returnType: "string", visibility: "public" },
      ],
    },
    {
      key: "concrete_prototype_b",
      type: "class",
      name: "ConcretePrototypeB",
      description: "Implements cloning for type B",
      isAbstract: false,
      attributes: [{ name: "fieldB", type: "number", visibility: "private" }],
      methods: [
        { name: "clone", returnType: "IPrototype", visibility: "public" },
        { name: "getFieldB", returnType: "number", visibility: "public" },
      ],
    },
    {
      key: "client",
      type: "class",
      name: "Client",
      description: "Creates new objects by cloning prototypes",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operation", returnType: "void", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "concrete_prototype_a", to: "prototype", type: "implementation" },
    { from: "concrete_prototype_b", to: "prototype", type: "implementation" },
    { from: "client", to: "prototype", type: "dependency", description: "clones" },
  ],
  layoutHints: [
    { key: "prototype", row: 0, col: 1 },
    { key: "concrete_prototype_a", row: 1, col: 0 },
    { key: "concrete_prototype_b", row: 1, col: 2 },
    { key: "client", row: 0, col: 3 },
  ],
};

const SINGLETON: DesignPatternTemplate = {
  id: "singleton",
  name: "Singleton",
  category: "creational",
  description: "Ensure a class has only one instance, and provide a global point of access to it.",
  reference: "GoF - Creational",
  entities: [
    {
      key: "singleton",
      type: "class",
      name: "Singleton",
      description: "The Singleton class with private constructor",
      isAbstract: false,
      attributes: [{ name: "instance", type: "Singleton", visibility: "private", isStatic: true }],
      methods: [
        { name: "getInstance", returnType: "Singleton", visibility: "public", isStatic: true },
        { name: "businessLogic", returnType: "void", visibility: "public" },
      ],
    },
  ],
  relationships: [],
  layoutHints: [{ key: "singleton", row: 0, col: 0 }],
};

// =============================================================================
// STRUCTURAL PATTERNS (7)
// =============================================================================

const ADAPTER: DesignPatternTemplate = {
  id: "adapter",
  name: "Adapter",
  category: "structural",
  description: "Convert the interface of a class into another interface clients expect.",
  reference: "GoF - Structural",
  entities: [
    {
      key: "target",
      type: "interface",
      name: "ITarget",
      description: "The interface that the client expects",
      methods: [{ name: "request", returnType: "string" }],
    },
    {
      key: "adapter",
      type: "class",
      name: "Adapter",
      description: "Adapts Adaptee to Target interface",
      isAbstract: false,
      attributes: [{ name: "adaptee", type: "Adaptee", visibility: "private" }],
      methods: [{ name: "request", returnType: "string", visibility: "public" }],
    },
    {
      key: "adaptee",
      type: "class",
      name: "Adaptee",
      description: "The existing class with incompatible interface",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "specificRequest", returnType: "string", visibility: "public" }],
    },
    {
      key: "client",
      type: "class",
      name: "Client",
      description: "Works with objects via Target interface",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operation", returnType: "void", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "adapter", to: "target", type: "implementation" },
    { from: "adapter", to: "adaptee", type: "composition", description: "wraps" },
    { from: "client", to: "target", type: "dependency", description: "uses" },
  ],
  layoutHints: [
    { key: "client", row: 0, col: 0 },
    { key: "target", row: 0, col: 1 },
    { key: "adapter", row: 1, col: 1 },
    { key: "adaptee", row: 1, col: 2 },
  ],
};

const BRIDGE: DesignPatternTemplate = {
  id: "bridge",
  name: "Bridge",
  category: "structural",
  description: "Decouple an abstraction from its implementation so that the two can vary independently.",
  reference: "GoF - Structural",
  entities: [
    {
      key: "abstraction",
      type: "class",
      name: "Abstraction",
      description: "Defines the abstraction's interface",
      isAbstract: false,
      attributes: [{ name: "implementation", type: "IImplementation", visibility: "protected" }],
      methods: [{ name: "operation", returnType: "string", visibility: "public" }],
    },
    {
      key: "refined_abstraction",
      type: "class",
      name: "RefinedAbstraction",
      description: "Extends the abstraction",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operation", returnType: "string", visibility: "public" }],
    },
    {
      key: "implementation",
      type: "interface",
      name: "IImplementation",
      description: "Interface for implementation classes",
      methods: [{ name: "operationImpl", returnType: "string" }],
    },
    {
      key: "concrete_impl_a",
      type: "class",
      name: "ConcreteImplementationA",
      description: "Implementation variant A",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationImpl", returnType: "string", visibility: "public" }],
    },
    {
      key: "concrete_impl_b",
      type: "class",
      name: "ConcreteImplementationB",
      description: "Implementation variant B",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationImpl", returnType: "string", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "refined_abstraction", to: "abstraction", type: "inheritance" },
    { from: "abstraction", to: "implementation", type: "aggregation", description: "uses" },
    { from: "concrete_impl_a", to: "implementation", type: "implementation" },
    { from: "concrete_impl_b", to: "implementation", type: "implementation" },
  ],
  layoutHints: [
    { key: "abstraction", row: 0, col: 0 },
    { key: "refined_abstraction", row: 1, col: 0 },
    { key: "implementation", row: 0, col: 2 },
    { key: "concrete_impl_a", row: 1, col: 1 },
    { key: "concrete_impl_b", row: 1, col: 3 },
  ],
};

const COMPOSITE: DesignPatternTemplate = {
  id: "composite",
  name: "Composite",
  category: "structural",
  description: "Compose objects into tree structures to represent part-whole hierarchies.",
  reference: "GoF - Structural",
  entities: [
    {
      key: "component",
      type: "interface",
      name: "IComponent",
      description: "Common interface for leaves and composites",
      methods: [
        { name: "operation", returnType: "string" },
        { name: "add", returnType: "void", parameters: [{ name: "component", type: "IComponent" }] },
        { name: "remove", returnType: "void", parameters: [{ name: "component", type: "IComponent" }] },
        { name: "getChild", returnType: "IComponent", parameters: [{ name: "index", type: "number" }] },
      ],
    },
    {
      key: "leaf",
      type: "class",
      name: "Leaf",
      description: "Represents leaf objects in composition",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operation", returnType: "string", visibility: "public" }],
    },
    {
      key: "composite",
      type: "class",
      name: "Composite",
      description: "Stores child components",
      isAbstract: false,
      attributes: [{ name: "children", type: "IComponent[]", visibility: "private" }],
      methods: [
        { name: "operation", returnType: "string", visibility: "public" },
        { name: "add", returnType: "void", visibility: "public" },
        { name: "remove", returnType: "void", visibility: "public" },
        { name: "getChild", returnType: "IComponent", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "leaf", to: "component", type: "implementation" },
    { from: "composite", to: "component", type: "implementation" },
    { from: "composite", to: "component", type: "aggregation", description: "contains", cardinality: "0..*" },
  ],
  layoutHints: [
    { key: "component", row: 0, col: 1 },
    { key: "leaf", row: 1, col: 0 },
    { key: "composite", row: 1, col: 2 },
  ],
};

const DECORATOR: DesignPatternTemplate = {
  id: "decorator",
  name: "Decorator",
  category: "structural",
  description: "Attach additional responsibilities to an object dynamically.",
  reference: "GoF - Structural",
  entities: [
    {
      key: "component",
      type: "interface",
      name: "IComponent",
      description: "Interface for objects that can be decorated",
      methods: [{ name: "operation", returnType: "string" }],
    },
    {
      key: "concrete_component",
      type: "class",
      name: "ConcreteComponent",
      description: "The object to be decorated",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operation", returnType: "string", visibility: "public" }],
    },
    {
      key: "base_decorator",
      type: "class",
      name: "BaseDecorator",
      description: "Base class for decorators",
      isAbstract: true,
      attributes: [{ name: "wrappee", type: "IComponent", visibility: "protected" }],
      methods: [{ name: "operation", returnType: "string", visibility: "public" }],
    },
    {
      key: "concrete_decorator_a",
      type: "class",
      name: "ConcreteDecoratorA",
      description: "Adds behavior A",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operation", returnType: "string", visibility: "public" }],
    },
    {
      key: "concrete_decorator_b",
      type: "class",
      name: "ConcreteDecoratorB",
      description: "Adds behavior B",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "operation", returnType: "string", visibility: "public" },
        { name: "extraBehavior", returnType: "void", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_component", to: "component", type: "implementation" },
    { from: "base_decorator", to: "component", type: "implementation" },
    { from: "base_decorator", to: "component", type: "aggregation", description: "wraps" },
    { from: "concrete_decorator_a", to: "base_decorator", type: "inheritance" },
    { from: "concrete_decorator_b", to: "base_decorator", type: "inheritance" },
  ],
  layoutHints: [
    { key: "component", row: 0, col: 1 },
    { key: "concrete_component", row: 1, col: 0 },
    { key: "base_decorator", row: 1, col: 2 },
    { key: "concrete_decorator_a", row: 2, col: 1 },
    { key: "concrete_decorator_b", row: 2, col: 3 },
  ],
};

const FACADE: DesignPatternTemplate = {
  id: "facade",
  name: "Facade",
  category: "structural",
  description: "Provide a unified interface to a set of interfaces in a subsystem.",
  reference: "GoF - Structural",
  entities: [
    {
      key: "facade",
      type: "class",
      name: "Facade",
      description: "Provides simple interface to complex subsystem",
      isAbstract: false,
      attributes: [
        { name: "subsystemA", type: "SubsystemA", visibility: "private" },
        { name: "subsystemB", type: "SubsystemB", visibility: "private" },
        { name: "subsystemC", type: "SubsystemC", visibility: "private" },
      ],
      methods: [
        { name: "operation", returnType: "string", visibility: "public" },
        { name: "anotherOperation", returnType: "string", visibility: "public" },
      ],
    },
    {
      key: "subsystem_a",
      type: "class",
      name: "SubsystemA",
      description: "Subsystem class A",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationA", returnType: "string", visibility: "public" }],
    },
    {
      key: "subsystem_b",
      type: "class",
      name: "SubsystemB",
      description: "Subsystem class B",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationB", returnType: "string", visibility: "public" }],
    },
    {
      key: "subsystem_c",
      type: "class",
      name: "SubsystemC",
      description: "Subsystem class C",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "operationC", returnType: "string", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "facade", to: "subsystem_a", type: "composition" },
    { from: "facade", to: "subsystem_b", type: "composition" },
    { from: "facade", to: "subsystem_c", type: "composition" },
  ],
  layoutHints: [
    { key: "facade", row: 0, col: 1 },
    { key: "subsystem_a", row: 1, col: 0 },
    { key: "subsystem_b", row: 1, col: 1 },
    { key: "subsystem_c", row: 1, col: 2 },
  ],
};

const FLYWEIGHT: DesignPatternTemplate = {
  id: "flyweight",
  name: "Flyweight",
  category: "structural",
  description: "Use sharing to support large numbers of fine-grained objects efficiently.",
  reference: "GoF - Structural",
  entities: [
    {
      key: "flyweight",
      type: "interface",
      name: "IFlyweight",
      description: "Interface for flyweight objects",
      methods: [{ name: "operation", returnType: "void", parameters: [{ name: "extrinsicState", type: "string" }] }],
    },
    {
      key: "concrete_flyweight",
      type: "class",
      name: "ConcreteFlyweight",
      description: "Stores intrinsic state",
      isAbstract: false,
      attributes: [{ name: "intrinsicState", type: "string", visibility: "private" }],
      methods: [{ name: "operation", returnType: "void", visibility: "public" }],
    },
    {
      key: "flyweight_factory",
      type: "class",
      name: "FlyweightFactory",
      description: "Creates and manages flyweight objects",
      isAbstract: false,
      attributes: [{ name: "cache", type: "Map<string, IFlyweight>", visibility: "private" }],
      methods: [{ name: "getFlyweight", returnType: "IFlyweight", visibility: "public", parameters: [{ name: "key", type: "string" }] }],
    },
    {
      key: "client",
      type: "class",
      name: "Client",
      description: "Stores extrinsic state",
      isAbstract: false,
      attributes: [{ name: "extrinsicState", type: "string", visibility: "private" }],
      methods: [{ name: "operation", returnType: "void", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "concrete_flyweight", to: "flyweight", type: "implementation" },
    { from: "flyweight_factory", to: "flyweight", type: "aggregation", description: "manages", cardinality: "0..*" },
    { from: "client", to: "flyweight_factory", type: "dependency", description: "uses" },
  ],
  layoutHints: [
    { key: "flyweight", row: 0, col: 1 },
    { key: "concrete_flyweight", row: 1, col: 1 },
    { key: "flyweight_factory", row: 0, col: 0 },
    { key: "client", row: 1, col: 0 },
  ],
};

const PROXY: DesignPatternTemplate = {
  id: "proxy",
  name: "Proxy",
  category: "structural",
  description: "Provide a surrogate or placeholder for another object to control access to it.",
  reference: "GoF - Structural",
  entities: [
    {
      key: "subject",
      type: "interface",
      name: "ISubject",
      description: "Common interface for RealSubject and Proxy",
      methods: [{ name: "request", returnType: "void" }],
    },
    {
      key: "real_subject",
      type: "class",
      name: "RealSubject",
      description: "The real object the proxy represents",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "request", returnType: "void", visibility: "public" }],
    },
    {
      key: "proxy",
      type: "class",
      name: "Proxy",
      description: "Controls access to RealSubject",
      isAbstract: false,
      attributes: [{ name: "realSubject", type: "RealSubject", visibility: "private" }],
      methods: [
        { name: "request", returnType: "void", visibility: "public" },
        { name: "checkAccess", returnType: "boolean", visibility: "private" },
        { name: "logAccess", returnType: "void", visibility: "private" },
      ],
    },
  ],
  relationships: [
    { from: "real_subject", to: "subject", type: "implementation" },
    { from: "proxy", to: "subject", type: "implementation" },
    { from: "proxy", to: "real_subject", type: "aggregation", description: "controls" },
  ],
  layoutHints: [
    { key: "subject", row: 0, col: 1 },
    { key: "real_subject", row: 1, col: 0 },
    { key: "proxy", row: 1, col: 2 },
  ],
};

// =============================================================================
// BEHAVIORAL PATTERNS (11)
// =============================================================================

const CHAIN_OF_RESPONSIBILITY: DesignPatternTemplate = {
  id: "chain-of-responsibility",
  name: "Chain of Responsibility",
  category: "behavioral",
  description: "Avoid coupling the sender of a request to its receiver by giving more than one object a chance to handle the request.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "handler",
      type: "interface",
      name: "IHandler",
      description: "Interface for handling requests",
      methods: [
        { name: "setNext", returnType: "IHandler", parameters: [{ name: "handler", type: "IHandler" }] },
        { name: "handle", returnType: "string", parameters: [{ name: "request", type: "string" }] },
      ],
    },
    {
      key: "base_handler",
      type: "class",
      name: "BaseHandler",
      description: "Default chaining behavior",
      isAbstract: true,
      attributes: [{ name: "nextHandler", type: "IHandler", visibility: "private" }],
      methods: [
        { name: "setNext", returnType: "IHandler", visibility: "public" },
        { name: "handle", returnType: "string", visibility: "public" },
      ],
    },
    {
      key: "concrete_handler_a",
      type: "class",
      name: "ConcreteHandlerA",
      description: "Handles specific request type A",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "handle", returnType: "string", visibility: "public" }],
    },
    {
      key: "concrete_handler_b",
      type: "class",
      name: "ConcreteHandlerB",
      description: "Handles specific request type B",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "handle", returnType: "string", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "base_handler", to: "handler", type: "implementation" },
    { from: "concrete_handler_a", to: "base_handler", type: "inheritance" },
    { from: "concrete_handler_b", to: "base_handler", type: "inheritance" },
    { from: "base_handler", to: "handler", type: "aggregation", description: "next" },
  ],
  layoutHints: [
    { key: "handler", row: 0, col: 1 },
    { key: "base_handler", row: 1, col: 1 },
    { key: "concrete_handler_a", row: 2, col: 0 },
    { key: "concrete_handler_b", row: 2, col: 2 },
  ],
};

const COMMAND: DesignPatternTemplate = {
  id: "command",
  name: "Command",
  category: "behavioral",
  description: "Encapsulate a request as an object, thereby letting you parameterize clients with different requests.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "command",
      type: "interface",
      name: "ICommand",
      description: "Interface for command execution",
      methods: [{ name: "execute", returnType: "void" }],
    },
    {
      key: "concrete_command",
      type: "class",
      name: "ConcreteCommand",
      description: "Implements command, delegates to receiver",
      isAbstract: false,
      attributes: [
        { name: "receiver", type: "Receiver", visibility: "private" },
        { name: "params", type: "string", visibility: "private" },
      ],
      methods: [{ name: "execute", returnType: "void", visibility: "public" }],
    },
    {
      key: "receiver",
      type: "class",
      name: "Receiver",
      description: "Knows how to perform the operations",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "operationA", returnType: "void", visibility: "public" },
        { name: "operationB", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "invoker",
      type: "class",
      name: "Invoker",
      description: "Asks the command to carry out the request",
      isAbstract: false,
      attributes: [{ name: "command", type: "ICommand", visibility: "private" }],
      methods: [
        { name: "setCommand", returnType: "void", visibility: "public" },
        { name: "executeCommand", returnType: "void", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_command", to: "command", type: "implementation" },
    { from: "concrete_command", to: "receiver", type: "association", description: "uses" },
    { from: "invoker", to: "command", type: "aggregation", description: "invokes" },
  ],
  layoutHints: [
    { key: "invoker", row: 0, col: 0 },
    { key: "command", row: 0, col: 1 },
    { key: "concrete_command", row: 1, col: 1 },
    { key: "receiver", row: 1, col: 2 },
  ],
};

const ITERATOR: DesignPatternTemplate = {
  id: "iterator",
  name: "Iterator",
  category: "behavioral",
  description: "Provide a way to access the elements of an aggregate object sequentially without exposing its underlying representation.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "iterator",
      type: "interface",
      name: "IIterator",
      description: "Interface for traversing a collection",
      methods: [
        { name: "next", returnType: "T" },
        { name: "hasNext", returnType: "boolean" },
        { name: "current", returnType: "T" },
      ],
    },
    {
      key: "concrete_iterator",
      type: "class",
      name: "ConcreteIterator",
      description: "Implements traversal for a collection",
      isAbstract: false,
      attributes: [
        { name: "collection", type: "ConcreteCollection", visibility: "private" },
        { name: "position", type: "number", visibility: "private" },
      ],
      methods: [
        { name: "next", returnType: "T", visibility: "public" },
        { name: "hasNext", returnType: "boolean", visibility: "public" },
        { name: "current", returnType: "T", visibility: "public" },
      ],
    },
    {
      key: "iterable",
      type: "interface",
      name: "IIterable",
      description: "Interface for creating iterators",
      methods: [{ name: "createIterator", returnType: "IIterator" }],
    },
    {
      key: "concrete_collection",
      type: "class",
      name: "ConcreteCollection",
      description: "Collection that can be iterated",
      isAbstract: false,
      attributes: [{ name: "items", type: "T[]", visibility: "private" }],
      methods: [
        { name: "createIterator", returnType: "IIterator", visibility: "public" },
        { name: "getItems", returnType: "T[]", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_iterator", to: "iterator", type: "implementation" },
    { from: "concrete_collection", to: "iterable", type: "implementation" },
    { from: "concrete_collection", to: "concrete_iterator", type: "dependency", description: "creates" },
  ],
  layoutHints: [
    { key: "iterator", row: 0, col: 0 },
    { key: "concrete_iterator", row: 1, col: 0 },
    { key: "iterable", row: 0, col: 2 },
    { key: "concrete_collection", row: 1, col: 2 },
  ],
};

const MEDIATOR: DesignPatternTemplate = {
  id: "mediator",
  name: "Mediator",
  category: "behavioral",
  description: "Define an object that encapsulates how a set of objects interact.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "mediator",
      type: "interface",
      name: "IMediator",
      description: "Interface for communication between colleagues",
      methods: [{ name: "notify", returnType: "void", parameters: [{ name: "sender", type: "IColleague" }, { name: "event", type: "string" }] }],
    },
    {
      key: "concrete_mediator",
      type: "class",
      name: "ConcreteMediator",
      description: "Coordinates colleague interactions",
      isAbstract: false,
      attributes: [
        { name: "colleagueA", type: "ColleagueA", visibility: "private" },
        { name: "colleagueB", type: "ColleagueB", visibility: "private" },
      ],
      methods: [{ name: "notify", returnType: "void", visibility: "public" }],
    },
    {
      key: "colleague",
      type: "interface",
      name: "IColleague",
      description: "Base interface for colleagues",
      methods: [{ name: "setMediator", returnType: "void", parameters: [{ name: "mediator", type: "IMediator" }] }],
    },
    {
      key: "colleague_a",
      type: "class",
      name: "ColleagueA",
      description: "Colleague component A",
      isAbstract: false,
      attributes: [{ name: "mediator", type: "IMediator", visibility: "protected" }],
      methods: [
        { name: "setMediator", returnType: "void", visibility: "public" },
        { name: "doA", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "colleague_b",
      type: "class",
      name: "ColleagueB",
      description: "Colleague component B",
      isAbstract: false,
      attributes: [{ name: "mediator", type: "IMediator", visibility: "protected" }],
      methods: [
        { name: "setMediator", returnType: "void", visibility: "public" },
        { name: "doB", returnType: "void", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_mediator", to: "mediator", type: "implementation" },
    { from: "colleague_a", to: "colleague", type: "implementation" },
    { from: "colleague_b", to: "colleague", type: "implementation" },
    { from: "concrete_mediator", to: "colleague_a", type: "association" },
    { from: "concrete_mediator", to: "colleague_b", type: "association" },
    { from: "colleague_a", to: "mediator", type: "dependency", description: "notifies" },
    { from: "colleague_b", to: "mediator", type: "dependency", description: "notifies" },
  ],
  layoutHints: [
    { key: "mediator", row: 0, col: 1 },
    { key: "concrete_mediator", row: 1, col: 1 },
    { key: "colleague", row: 0, col: 3 },
    { key: "colleague_a", row: 1, col: 2 },
    { key: "colleague_b", row: 1, col: 4 },
  ],
};

const MEMENTO: DesignPatternTemplate = {
  id: "memento",
  name: "Memento",
  category: "behavioral",
  description: "Without violating encapsulation, capture and externalize an object's internal state so that the object can be restored to this state later.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "memento",
      type: "interface",
      name: "IMemento",
      description: "Interface for memento objects",
      methods: [
        { name: "getState", returnType: "string" },
        { name: "getName", returnType: "string" },
        { name: "getDate", returnType: "Date" },
      ],
    },
    {
      key: "concrete_memento",
      type: "class",
      name: "ConcreteMemento",
      description: "Stores originator state",
      isAbstract: false,
      attributes: [
        { name: "state", type: "string", visibility: "private" },
        { name: "date", type: "Date", visibility: "private" },
      ],
      methods: [
        { name: "getState", returnType: "string", visibility: "public" },
        { name: "getName", returnType: "string", visibility: "public" },
        { name: "getDate", returnType: "Date", visibility: "public" },
      ],
    },
    {
      key: "originator",
      type: "class",
      name: "Originator",
      description: "Creates and restores mementos",
      isAbstract: false,
      attributes: [{ name: "state", type: "string", visibility: "private" }],
      methods: [
        { name: "save", returnType: "IMemento", visibility: "public" },
        { name: "restore", returnType: "void", visibility: "public", parameters: [{ name: "memento", type: "IMemento" }] },
        { name: "doSomething", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "caretaker",
      type: "class",
      name: "Caretaker",
      description: "Keeps track of mementos",
      isAbstract: false,
      attributes: [
        { name: "mementos", type: "IMemento[]", visibility: "private" },
        { name: "originator", type: "Originator", visibility: "private" },
      ],
      methods: [
        { name: "backup", returnType: "void", visibility: "public" },
        { name: "undo", returnType: "void", visibility: "public" },
        { name: "showHistory", returnType: "void", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_memento", to: "memento", type: "implementation" },
    { from: "originator", to: "memento", type: "dependency", description: "creates" },
    { from: "caretaker", to: "memento", type: "aggregation", description: "stores", cardinality: "0..*" },
    { from: "caretaker", to: "originator", type: "association", description: "uses" },
  ],
  layoutHints: [
    { key: "memento", row: 0, col: 1 },
    { key: "concrete_memento", row: 1, col: 1 },
    { key: "originator", row: 0, col: 2 },
    { key: "caretaker", row: 0, col: 0 },
  ],
};

const OBSERVER: DesignPatternTemplate = {
  id: "observer",
  name: "Observer",
  category: "behavioral",
  description: "Define a one-to-many dependency between objects so that when one object changes state, all its dependents are notified and updated automatically.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "observer",
      type: "interface",
      name: "IObserver",
      description: "Interface for objects that should be notified",
      methods: [{ name: "update", returnType: "void", parameters: [{ name: "subject", type: "ISubject" }] }],
    },
    {
      key: "subject",
      type: "interface",
      name: "ISubject",
      description: "Interface for observable objects",
      methods: [
        { name: "attach", returnType: "void", parameters: [{ name: "observer", type: "IObserver" }] },
        { name: "detach", returnType: "void", parameters: [{ name: "observer", type: "IObserver" }] },
        { name: "notify", returnType: "void" },
      ],
    },
    {
      key: "concrete_subject",
      type: "class",
      name: "ConcreteSubject",
      description: "Stores state of interest",
      isAbstract: false,
      attributes: [
        { name: "state", type: "any", visibility: "private" },
        { name: "observers", type: "IObserver[]", visibility: "private" },
      ],
      methods: [
        { name: "attach", returnType: "void", visibility: "public" },
        { name: "detach", returnType: "void", visibility: "public" },
        { name: "notify", returnType: "void", visibility: "public" },
        { name: "getState", returnType: "any", visibility: "public" },
        { name: "setState", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "concrete_observer",
      type: "class",
      name: "ConcreteObserver",
      description: "Reacts to state changes",
      isAbstract: false,
      attributes: [{ name: "observerState", type: "any", visibility: "private" }],
      methods: [{ name: "update", returnType: "void", visibility: "public" }],
    },
  ],
  relationships: [
    { from: "concrete_subject", to: "subject", type: "implementation" },
    { from: "concrete_observer", to: "observer", type: "implementation" },
    { from: "concrete_subject", to: "observer", type: "aggregation", description: "notifies", cardinality: "0..*" },
  ],
  layoutHints: [
    { key: "subject", row: 0, col: 0 },
    { key: "observer", row: 0, col: 2 },
    { key: "concrete_subject", row: 1, col: 0 },
    { key: "concrete_observer", row: 1, col: 2 },
  ],
};

const STATE: DesignPatternTemplate = {
  id: "state",
  name: "State",
  category: "behavioral",
  description: "Allow an object to alter its behavior when its internal state changes.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "state",
      type: "interface",
      name: "IState",
      description: "Interface for state-specific behavior",
      methods: [
        { name: "handle1", returnType: "void" },
        { name: "handle2", returnType: "void" },
      ],
    },
    {
      key: "concrete_state_a",
      type: "class",
      name: "ConcreteStateA",
      description: "State A implementation",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "handle1", returnType: "void", visibility: "public" },
        { name: "handle2", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "concrete_state_b",
      type: "class",
      name: "ConcreteStateB",
      description: "State B implementation",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "handle1", returnType: "void", visibility: "public" },
        { name: "handle2", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "context",
      type: "class",
      name: "Context",
      description: "Maintains current state",
      isAbstract: false,
      attributes: [{ name: "state", type: "IState", visibility: "private" }],
      methods: [
        { name: "setState", returnType: "void", visibility: "public", parameters: [{ name: "state", type: "IState" }] },
        { name: "request1", returnType: "void", visibility: "public" },
        { name: "request2", returnType: "void", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_state_a", to: "state", type: "implementation" },
    { from: "concrete_state_b", to: "state", type: "implementation" },
    { from: "context", to: "state", type: "aggregation", description: "current state" },
  ],
  layoutHints: [
    { key: "state", row: 0, col: 1 },
    { key: "concrete_state_a", row: 1, col: 0 },
    { key: "concrete_state_b", row: 1, col: 2 },
    { key: "context", row: 0, col: 3 },
  ],
};

const STRATEGY: DesignPatternTemplate = {
  id: "strategy",
  name: "Strategy",
  category: "behavioral",
  description: "Define a family of algorithms, encapsulate each one, and make them interchangeable.",
  reference: "GoF - Behavioral",
  languageNames: {
    python: { IStrategy: "StrategyProtocol" },
  },
  entities: [
    {
      key: "strategy",
      type: "interface",
      name: "IStrategy",
      description: "Interface for all supported algorithms",
      methods: [{ name: "execute", returnType: "void", parameters: [{ name: "data", type: "any" }] }],
    },
    {
      key: "concrete_strategy_a",
      type: "class",
      name: "ConcreteStrategyA",
      description: "Implements algorithm A",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "execute", returnType: "void", visibility: "public" }],
    },
    {
      key: "concrete_strategy_b",
      type: "class",
      name: "ConcreteStrategyB",
      description: "Implements algorithm B",
      isAbstract: false,
      attributes: [],
      methods: [{ name: "execute", returnType: "void", visibility: "public" }],
    },
    {
      key: "context",
      type: "class",
      name: "Context",
      description: "Maintains reference to a Strategy",
      isAbstract: false,
      attributes: [{ name: "strategy", type: "IStrategy", visibility: "private" }],
      methods: [
        { name: "setStrategy", returnType: "void", visibility: "public", parameters: [{ name: "strategy", type: "IStrategy" }] },
        { name: "executeStrategy", returnType: "void", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_strategy_a", to: "strategy", type: "implementation" },
    { from: "concrete_strategy_b", to: "strategy", type: "implementation" },
    { from: "context", to: "strategy", type: "aggregation", description: "uses" },
  ],
  layoutHints: [
    { key: "strategy", row: 0, col: 1 },
    { key: "concrete_strategy_a", row: 1, col: 0 },
    { key: "concrete_strategy_b", row: 1, col: 2 },
    { key: "context", row: 0, col: 3 },
  ],
};

const TEMPLATE_METHOD: DesignPatternTemplate = {
  id: "template-method",
  name: "Template Method",
  category: "behavioral",
  description: "Define the skeleton of an algorithm in an operation, deferring some steps to subclasses.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "abstract_class",
      type: "class",
      name: "AbstractClass",
      description: "Defines template method and abstract steps",
      isAbstract: true,
      attributes: [],
      methods: [
        { name: "templateMethod", returnType: "void", visibility: "public" },
        { name: "step1", returnType: "void", visibility: "protected", isAbstract: true },
        { name: "step2", returnType: "void", visibility: "protected", isAbstract: true },
        { name: "hook", returnType: "void", visibility: "protected" },
      ],
    },
    {
      key: "concrete_class_a",
      type: "class",
      name: "ConcreteClassA",
      description: "Implements steps for variant A",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "step1", returnType: "void", visibility: "protected" },
        { name: "step2", returnType: "void", visibility: "protected" },
      ],
    },
    {
      key: "concrete_class_b",
      type: "class",
      name: "ConcreteClassB",
      description: "Implements steps for variant B",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "step1", returnType: "void", visibility: "protected" },
        { name: "step2", returnType: "void", visibility: "protected" },
        { name: "hook", returnType: "void", visibility: "protected" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_class_a", to: "abstract_class", type: "inheritance" },
    { from: "concrete_class_b", to: "abstract_class", type: "inheritance" },
  ],
  layoutHints: [
    { key: "abstract_class", row: 0, col: 1 },
    { key: "concrete_class_a", row: 1, col: 0 },
    { key: "concrete_class_b", row: 1, col: 2 },
  ],
};

const VISITOR: DesignPatternTemplate = {
  id: "visitor",
  name: "Visitor",
  category: "behavioral",
  description: "Represent an operation to be performed on the elements of an object structure.",
  reference: "GoF - Behavioral",
  entities: [
    {
      key: "visitor",
      type: "interface",
      name: "IVisitor",
      description: "Declares visit methods for each element type",
      methods: [
        { name: "visitElementA", returnType: "void", parameters: [{ name: "element", type: "ElementA" }] },
        { name: "visitElementB", returnType: "void", parameters: [{ name: "element", type: "ElementB" }] },
      ],
    },
    {
      key: "concrete_visitor_1",
      type: "class",
      name: "ConcreteVisitor1",
      description: "Implements operation 1 for all elements",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "visitElementA", returnType: "void", visibility: "public" },
        { name: "visitElementB", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "concrete_visitor_2",
      type: "class",
      name: "ConcreteVisitor2",
      description: "Implements operation 2 for all elements",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "visitElementA", returnType: "void", visibility: "public" },
        { name: "visitElementB", returnType: "void", visibility: "public" },
      ],
    },
    {
      key: "element",
      type: "interface",
      name: "IElement",
      description: "Declares accept method",
      methods: [{ name: "accept", returnType: "void", parameters: [{ name: "visitor", type: "IVisitor" }] }],
    },
    {
      key: "element_a",
      type: "class",
      name: "ElementA",
      description: "Concrete element A",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "accept", returnType: "void", visibility: "public" },
        { name: "operationA", returnType: "string", visibility: "public" },
      ],
    },
    {
      key: "element_b",
      type: "class",
      name: "ElementB",
      description: "Concrete element B",
      isAbstract: false,
      attributes: [],
      methods: [
        { name: "accept", returnType: "void", visibility: "public" },
        { name: "operationB", returnType: "string", visibility: "public" },
      ],
    },
  ],
  relationships: [
    { from: "concrete_visitor_1", to: "visitor", type: "implementation" },
    { from: "concrete_visitor_2", to: "visitor", type: "implementation" },
    { from: "element_a", to: "element", type: "implementation" },
    { from: "element_b", to: "element", type: "implementation" },
    { from: "element", to: "visitor", type: "dependency", description: "accepts" },
  ],
  layoutHints: [
    { key: "visitor", row: 0, col: 0 },
    { key: "concrete_visitor_1", row: 1, col: 0 },
    { key: "concrete_visitor_2", row: 2, col: 0 },
    { key: "element", row: 0, col: 2 },
    { key: "element_a", row: 1, col: 2 },
    { key: "element_b", row: 2, col: 2 },
  ],
};

// =============================================================================
// Export All Templates
// =============================================================================

export const DESIGN_PATTERN_TEMPLATES: DesignPatternTemplate[] = [
  // Creational (5)
  FACTORY_METHOD,
  ABSTRACT_FACTORY,
  BUILDER,
  PROTOTYPE,
  SINGLETON,
  // Structural (7)
  ADAPTER,
  BRIDGE,
  COMPOSITE,
  DECORATOR,
  FACADE,
  FLYWEIGHT,
  PROXY,
  // Behavioral (11)
  CHAIN_OF_RESPONSIBILITY,
  COMMAND,
  ITERATOR,
  MEDIATOR,
  MEMENTO,
  OBSERVER,
  STATE,
  STRATEGY,
  TEMPLATE_METHOD,
  VISITOR,
];

// Helper to get templates by category
export function getTemplatesByCategory(category: PatternCategory): DesignPatternTemplate[] {
  return DESIGN_PATTERN_TEMPLATES.filter((t) => t.category === category);
}

// Helper to get template by id
export function getTemplateById(id: string): DesignPatternTemplate | undefined {
  return DESIGN_PATTERN_TEMPLATES.find((t) => t.id === id);
}
