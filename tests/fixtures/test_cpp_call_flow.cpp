// Test file for C++ call flow extraction
// Contains various C++ patterns for baseline tests

#include <iostream>
#include <vector>
#include <string>

// Simple helper function
int helper_function() {
    return 42;
}

// Function calling helper
int process_value(int x) {
    int result = helper_function();
    return x + result;
}

// Function with multiple calls
void complex_function(int a, int b) {
    int val1 = process_value(a);
    int val2 = helper_function();
    std::cout << val1 << " " << val2 << std::endl;
}

// Class with methods
class Calculator {
private:
    int result;

    int internal_add(int a, int b) {
        return a + b;
    }

public:
    Calculator() : result(0) {
        reset();
    }

    void reset() {
        result = 0;
    }

    void add(int value) {
        result = internal_add(result, value);
    }

    void subtract(int value) {
        result -= value;
    }

    int get_result() {
        return result;
    }

    void compute(int a, int b) {
        add(a);
        add(b);
        int extra = helper_function();
        result += extra;
    }
};

// Function using class
int calculate_total(const std::vector<int>& values) {
    Calculator calc;
    for (int val : values) {
        calc.add(val);
    }
    return calc.get_result();
}

// Main function
int main() {
    complex_function(1, 2);

    std::vector<int> nums = {1, 2, 3, 4, 5};
    int total = calculate_total(nums);
    std::cout << "Total: " << total << std::endl;

    Calculator c;
    c.compute(10, 20);
    std::cout << "Result: " << c.get_result() << std::endl;

    return 0;
}
