"""
Sample file for testing decision point detection in Call Flow extraction.

Contains various decision structures:
- if/else statements
- match/case statements (Python 3.10+)
- try/except statements
- ternary expressions
- Nested decision points

Note: Loops (for/while) are NOT treated as decision points per user preference.
"""


def validate(data: dict) -> bool:
    """Validate the data structure."""
    return "key" in data and data["key"] is not None


def process_priority(order):
    """Process a priority order."""
    send_express_notification(order)
    return "priority_processed"


def send_express_notification(order):
    """Send express delivery notification."""
    return f"express_notification_sent:{order}"


def process_standard(order):
    """Process a standard order."""
    queue_standard_processing(order)
    return "standard_processed"


def queue_standard_processing(order):
    """Queue order for standard processing."""
    return f"queued:{order}"


def finalize(order):
    """Finalize the order."""
    return f"finalized:{order}"


def process_order(order):
    """
    Process an order with decision points.

    This is the main test case for lazy extraction.
    Expected flow:
    1. validate() - always called
    2. if order.is_priority - DECISION POINT
        - TRUE branch: process_priority() -> send_express_notification()
        - FALSE branch: process_standard() -> queue_standard_processing()
    3. finalize() - always called (after decision)
    """
    validate(order)

    if order.get("is_priority"):
        process_priority(order)
    else:
        process_standard(order)

    finalize(order)


def handle_error(error_type):
    """Handle a specific error type."""
    return f"handled:{error_type}"


def log_error(msg):
    """Log an error message."""
    return f"logged:{msg}"


def cleanup():
    """Perform cleanup operations."""
    return "cleaned_up"


def risky_operation():
    """Perform a risky operation that might fail."""
    return "success"


def process_with_error_handling():
    """
    Process with try/except decision point.

    Expected flow:
    1. try block: risky_operation()
    2. except ValueError: handle_error("value")
    3. except TypeError: handle_error("type")
    4. finally: cleanup()
    """
    try:
        risky_operation()
    except ValueError:
        handle_error("value")
        log_error("ValueError occurred")
    except TypeError:
        handle_error("type")
    finally:
        cleanup()


def handle_status_active():
    """Handle active status."""
    return "active_handled"


def handle_status_pending():
    """Handle pending status."""
    return "pending_handled"


def handle_status_cancelled():
    """Handle cancelled status."""
    return "cancelled_handled"


def handle_status_unknown(status):
    """Handle unknown status."""
    return f"unknown:{status}"


def process_status(status: str):
    """
    Process status using match/case (Python 3.10+).

    Expected flow:
    1. match status - DECISION POINT
        - case "active": handle_status_active()
        - case "pending": handle_status_pending()
        - case "cancelled": handle_status_cancelled()
        - case _: handle_status_unknown()
    """
    match status:
        case "active":
            handle_status_active()
        case "pending":
            handle_status_pending()
        case "cancelled":
            handle_status_cancelled()
        case _:
            handle_status_unknown(status)


def get_default_value():
    """Get default value."""
    return "default"


def compute_value(x):
    """Compute a value."""
    return x * 2


def process_with_ternary(x):
    """
    Process with ternary expression (conditional).

    Expected flow:
    1. result = compute_value(x) if x > 0 else get_default_value()
    """
    result = compute_value(x) if x > 0 else get_default_value()
    return result


def deep_call_a():
    """Deep call A."""
    return "a"


def deep_call_b():
    """Deep call B."""
    return "b"


def deep_call_c():
    """Deep call C."""
    return "c"


def deep_call_d():
    """Deep call D."""
    return "d"


def nested_decision_inner(value):
    """Inner nested decision."""
    if value > 50:
        deep_call_c()
    else:
        deep_call_d()


def process_nested_decisions(x, y):
    """
    Process with nested decision points.

    Expected flow:
    1. if x > 0 - DECISION POINT 1
        - TRUE: if y > 10 - DECISION POINT 2 (nested)
            - TRUE: deep_call_a()
            - FALSE: deep_call_b()
        - FALSE: nested_decision_inner(y) - contains DECISION POINT 3
    """
    if x > 0:
        if y > 10:
            deep_call_a()
        else:
            deep_call_b()
    else:
        nested_decision_inner(y)


def iterate_items(items):
    """
    Iterate over items - NOT a decision point.

    Loops should be treated as linear flow per user preference.
    """
    for item in items:
        process_item(item)


def process_item(item):
    """Process a single item."""
    return f"processed:{item}"


def main():
    """Main entry point with multiple decision scenarios."""
    order = {"is_priority": True, "id": 123}
    process_order(order)

    process_with_error_handling()

    process_status("active")

    process_with_ternary(5)

    process_nested_decisions(1, 20)


if __name__ == "__main__":
    main()
