/**
 * Calculator module A - JavaScript
 */

function calculateTotal(items, taxRate) {
    // Calculate subtotal
    let subtotal = 0;
    for (const item of items) {
        subtotal += item.price * item.quantity;
    }

    // Apply tax
    const tax = subtotal * taxRate;
    const total = subtotal + tax;

    return {
        subtotal: subtotal,
        tax: tax,
        total: total
    };
}

function formatCurrency(amount) {
    return '$' + amount.toFixed(2);
}

function validateInput(value) {
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

module.exports = { calculateTotal, formatCurrency, validateInput };
