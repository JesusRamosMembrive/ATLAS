/**
 * Calculator module V2 - C++ (renamed version)
 */
#include <vector>
#include <string>

struct Product {
    double cost;
    int count;
};

struct Invoice {
    double baseAmount;
    double vatAmount;
    double grandTotal;
};

Invoice computeInvoice(const std::vector<Product>& products, double vatRate) {
    // Calculate subtotal
    double baseAmount = 0;
    for (const auto& product : products) {
        baseAmount += product.cost * product.count;
    }

    // Apply tax
    double vatAmount = baseAmount * vatRate;
    double grandTotal = baseAmount + vatAmount;

    return Invoice{baseAmount, vatAmount, grandTotal};
}

std::string formatMoney(double value) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "$%.2f", value);
    return std::string(buffer);
}

bool checkValue(double value) {
    if (value < 0) {
        return false;
    }
    return true;
}
