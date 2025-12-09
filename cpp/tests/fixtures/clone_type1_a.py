# Test file A for Type-1 clone detection
# Contains exact duplicate function

def validate_user(username, password):
    """Validate user credentials."""
    if not username:
        return False
    if not password:
        return False
    if len(password) < 8:
        return False
    return True


def process_data(data):
    """Process input data."""
    result = []
    for item in data:
        if item is not None:
            result.append(item * 2)
    return result


def calculate_total(items, tax_rate):
    """Calculate total with tax."""
    subtotal = 0
    for item in items:
        subtotal += item.price * item.quantity
    tax = subtotal * tax_rate
    return subtotal + tax


# This is unique to file A
def unique_function_a():
    return "only in A"
