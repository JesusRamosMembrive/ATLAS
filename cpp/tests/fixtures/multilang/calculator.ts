/**
 * Calculator module - TypeScript
 */

interface Item {
    price: number;
    quantity: number;
}

interface CalculationResult {
    subtotal: number;
    tax: number;
    total: number;
}

function calculateTotal(items: Item[], taxRate: number): CalculationResult {
    // Calculate subtotal
    let subtotal: number = 0;
    for (const item of items) {
        subtotal += item.price * item.quantity;
    }

    // Apply tax
    const tax: number = subtotal * taxRate;
    const total: number = subtotal + tax;

    return {
        subtotal: subtotal,
        tax: tax,
        total: total
    };
}

function formatCurrency(amount: number): string {
    return '$' + amount.toFixed(2);
}

function validateInput(value: unknown): boolean {
    if (value === null || value === undefined) {
        return false;
    }
    if (typeof value !== 'number') {
        return false;
    }
    if (value < 0) {
        return false;
    }
    return true;
}

export { calculateTotal, formatCurrency, validateInput };
