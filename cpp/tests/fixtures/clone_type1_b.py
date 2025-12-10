# Test file B for Type-1 clone detection
# Contains exact duplicate of functions from file A

def other_function():
    """Some other function."""
    return 42


def validate_user(username, password):
    """Validate user credentials."""
    if not username:
        return False
    if not password:
        return False
    if len(password) < 8:
        return False
    return True


def another_function():
    """Another function unique to B."""
    x = 1
    y = 2
    return x + y


def process_data(data):
    """Process input data."""
    result = []
    for item in data:
        if item is not None:
            result.append(item * 2)
    return result


# This is unique to file B
def unique_function_b():
    return "only in B"
