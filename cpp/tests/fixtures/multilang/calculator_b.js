/**
 * Calculator module B - JavaScript (renamed version)
 */

function computeSum(products, vatRate) {
    // Calculate subtotal
    let baseAmount = 0;
    for (const product of products) {
        baseAmount += product.price * product.quantity;
    }

    // Apply tax
    const vat = baseAmount * vatRate;
    const finalAmount = baseAmount + vat;

    return {
        subtotal: baseAmount,
        tax: vat,
        total: finalAmount
    };
}

function formatMoney(value) {
    return '$' + value.toFixed(2);
}

function checkInput(data) {
    if (data === null || data === undefined) {
        return false;
    }
    if (typeof data !== 'number') {
        return false;
    }
    if (data < 0) {
        return false;
    }
    return true;
}

module.exports = { computeSum, formatMoney, checkInput };
