/**
 * Sample file for testing decision point detection in Call Flow extraction (C++).
 *
 * Contains various decision structures:
 * - if/else statements
 * - switch/case statements
 * - try/catch statements
 * - ternary expressions
 * - Nested decision points
 *
 * Note: Loops (for/while) are NOT treated as decision points per user preference.
 */

#include <string>
#include <map>
#include <stdexcept>
#include <vector>

struct Order {
    bool is_priority;
    int id;
    std::string status;
};

// Forward declarations
void validate(const Order& order);
void process_priority(const Order& order);
void send_express_notification(const Order& order);
void process_standard(const Order& order);
void queue_standard_processing(const Order& order);
void finalize(const Order& order);
void handle_error(const std::string& error_type);
void log_error(const std::string& msg);
void cleanup();
void risky_operation();
void handle_status_active();
void handle_status_pending();
void handle_status_cancelled();
void handle_status_unknown(int status);
int get_default_value();
int compute_value(int x);
void deep_call_a();
void deep_call_b();
void deep_call_c();
void deep_call_d();
void nested_decision_inner(int value);
void process_item(const std::string& item);

// Simple helper functions

void validate(const Order& order) {
    // Validate the order structure
}

void process_priority(const Order& order) {
    // Process a priority order
    send_express_notification(order);
}

void send_express_notification(const Order& order) {
    // Send express delivery notification
}

void process_standard(const Order& order) {
    // Process a standard order
    queue_standard_processing(order);
}

void queue_standard_processing(const Order& order) {
    // Queue order for standard processing
}

void finalize(const Order& order) {
    // Finalize the order
}

/**
 * Process an order with decision points.
 *
 * This is the main test case for lazy extraction.
 * Expected flow:
 * 1. validate() - always called
 * 2. if order.is_priority - DECISION POINT
 *    - TRUE branch: process_priority() -> send_express_notification()
 *    - FALSE branch: process_standard() -> queue_standard_processing()
 * 3. finalize() - always called (after decision)
 */
void process_order(const Order& order) {
    validate(order);

    if (order.is_priority) {
        process_priority(order);
    } else {
        process_standard(order);
    }

    finalize(order);
}

void handle_error(const std::string& error_type) {
    // Handle a specific error type
}

void log_error(const std::string& msg) {
    // Log an error message
}

void cleanup() {
    // Perform cleanup operations
}

void risky_operation() {
    // Perform a risky operation that might fail
}

/**
 * Process with try/catch decision point.
 *
 * Expected flow:
 * 1. try block: risky_operation()
 * 2. catch runtime_error: handle_error("runtime")
 * 3. catch logic_error: handle_error("logic")
 */
void process_with_error_handling() {
    try {
        risky_operation();
    } catch (const std::runtime_error& e) {
        handle_error("runtime");
        log_error("Runtime error occurred");
    } catch (const std::logic_error& e) {
        handle_error("logic");
    }
}

void handle_status_active() {
    // Handle active status
}

void handle_status_pending() {
    // Handle pending status
}

void handle_status_cancelled() {
    // Handle cancelled status
}

void handle_status_unknown(int status) {
    // Handle unknown status
}

/**
 * Process status using switch/case.
 *
 * Expected flow:
 * 1. switch status - DECISION POINT
 *    - case 1: handle_status_active()
 *    - case 2: handle_status_pending()
 *    - case 3: handle_status_cancelled()
 *    - default: handle_status_unknown()
 */
void process_status(int status) {
    switch (status) {
        case 1:
            handle_status_active();
            break;
        case 2:
            handle_status_pending();
            break;
        case 3:
            handle_status_cancelled();
            break;
        default:
            handle_status_unknown(status);
            break;
    }
}

int get_default_value() {
    // Get default value
    return 0;
}

int compute_value(int x) {
    // Compute a value
    return x * 2;
}

/**
 * Process with ternary expression (conditional).
 *
 * Expected flow:
 * 1. result = (x > 0) ? compute_value(x) : get_default_value()
 */
int process_with_ternary(int x) {
    int result = (x > 0) ? compute_value(x) : get_default_value();
    return result;
}

void deep_call_a() {
    // Deep call A
}

void deep_call_b() {
    // Deep call B
}

void deep_call_c() {
    // Deep call C
}

void deep_call_d() {
    // Deep call D
}

/**
 * Inner nested decision.
 */
void nested_decision_inner(int value) {
    if (value > 50) {
        deep_call_c();
    } else {
        deep_call_d();
    }
}

/**
 * Process with nested decision points.
 *
 * Expected flow:
 * 1. if x > 0 - DECISION POINT 1
 *    - TRUE: if y > 10 - DECISION POINT 2 (nested)
 *        - TRUE: deep_call_a()
 *        - FALSE: deep_call_b()
 *    - FALSE: nested_decision_inner(y) - contains DECISION POINT 3
 */
void process_nested_decisions(int x, int y) {
    if (x > 0) {
        if (y > 10) {
            deep_call_a();
        } else {
            deep_call_b();
        }
    } else {
        nested_decision_inner(y);
    }
}

void process_item(const std::string& item) {
    // Process a single item
}

/**
 * Iterate over items - NOT a decision point.
 *
 * Loops should be treated as linear flow per user preference.
 */
void iterate_items(const std::vector<std::string>& items) {
    for (const auto& item : items) {
        process_item(item);
    }
}

/**
 * Main entry point with multiple decision scenarios.
 */
int main() {
    Order order = {true, 123, "active"};
    process_order(order);

    process_with_error_handling();

    process_status(1);

    process_with_ternary(5);

    process_nested_decisions(1, 20);

    return 0;
}
