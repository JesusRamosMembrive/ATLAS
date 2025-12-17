// Test file for TypeScript call flow extraction
// This file contains various TypeScript/JavaScript patterns

// Simple function
function greet(name: string): string {
  return `Hello, ${name}!`;
}

// Arrow function
const add = (a: number, b: number): number => {
  return a + b;
};

// Function calling other functions
function processUser(name: string, age: number): void {
  const greeting = greet(name);
  const total = add(age, 10);
  console.log(greeting, total);
}

// Class with methods
class Calculator {
  private result: number = 0;

  constructor() {
    this.reset();
  }

  add(value: number): Calculator {
    this.result = this.internalAdd(this.result, value);
    return this;
  }

  private internalAdd(a: number, b: number): number {
    return a + b;
  }

  subtract(value: number): Calculator {
    this.result -= value;
    return this;
  }

  multiply(value: number): Calculator {
    this.result *= value;
    return this;
  }

  getResult(): number {
    return this.result;
  }

  reset(): void {
    this.result = 0;
  }
}

// Function that uses the class
function calculateTotal(values: number[]): number {
  const calc = new Calculator();
  for (const val of values) {
    calc.add(val);
  }
  return calc.getResult();
}

// Complex function with multiple calls
function complexOperation(data: string[]): string {
  const processed = data.map((item) => item.toUpperCase());
  const first = processed[0] || "";
  const greeting = greet(first);
  const total = calculateTotal([1, 2, 3]);
  return `${greeting} - Total: ${total}`;
}

// Async function
async function fetchData(url: string): Promise<string> {
  const response = await fetch(url);
  return response.text();
}

// Function with callbacks
function withCallback(callback: () => void): void {
  console.log("Before callback");
  callback();
  console.log("After callback");
}

// Export default function
export default function main(): void {
  processUser("John", 30);
  const result = complexOperation(["hello", "world"]);
  console.log(result);
}

// Named export
export function helper(): number {
  return add(1, 2);
}
