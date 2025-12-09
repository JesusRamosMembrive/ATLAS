/**
 * Calculator module - C++
 */
#include <vector>
#include <string>

struct Item {
    double price;
    int quantity;
};

struct Result {
    double subtotal;
    double tax;
    double total;
};

Result calculateTotal(const std::vector<Item>& items, double taxRate) {
    // Calculate subtotal
    double subtotal = 0;
    for (const auto& item : items) {
        subtotal += item.price * item.quantity;
    }

    // Apply tax
    double tax = subtotal * taxRate;
    double total = subtotal + tax;

    return Result{subtotal, tax, total};
}

std::string formatCurrency(double amount) {
    char buffer[32];
    snprintf(buffer, sizeof(buffer), "$%.2f", amount);
    return std::string(buffer);
}

bool validateInput(double value) {
    if (value < 0) {
        return false;
    }
    return true;
}
