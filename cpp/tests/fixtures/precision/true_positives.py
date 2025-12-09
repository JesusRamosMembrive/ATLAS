"""True Positive Test Cases - Should be detected as clones."""

# CASE 1: Exact duplicate functions (must detect)
def calculate_total_a(items, tax_rate):
    """Calculate total with tax."""
    subtotal = sum(item.price for item in items)
    tax = subtotal * tax_rate
    total = subtotal + tax
    return total

def calculate_total_b(items, tax_rate):
    """Calculate total with tax."""
    subtotal = sum(item.price for item in items)
    tax = subtotal * tax_rate
    total = subtotal + tax
    return total


# CASE 2: Same logic different variable names (Type-1 after normalization)
def process_user_data(user_list, filter_func):
    """Process user data with filter."""
    result = []
    for user in user_list:
        if filter_func(user):
            result.append(user)
    return result

def process_customer_data(customer_list, predicate):
    """Process user data with filter."""
    result = []
    for customer in customer_list:
        if predicate(customer):
            result.append(customer)
    return result


# CASE 3: Whitespace and formatting differences (must detect)
def format_output_v1(data,prefix,suffix):
    output=prefix+str(data)+suffix
    return output

def format_output_v2(data, prefix, suffix):
    output = prefix + str(data) + suffix
    return output


# CASE 4: Comment differences only (must detect)
def validate_input_a(value):
    # Check if value is valid
    if value is None:
        return False
    if value < 0:
        return False
    return True

def validate_input_b(value):
    # Different comment here
    # Another comment line
    if value is None:
        return False
    if value < 0:
        return False
    return True


# CASE 5: Copied code block in different context
class ProcessorA:
    def run(self, data):
        # Common processing logic
        cleaned = data.strip()
        normalized = cleaned.lower()
        tokens = normalized.split()
        result = [t for t in tokens if len(t) > 2]
        return result

class ProcessorB:
    def execute(self, input_data):
        # Common processing logic
        cleaned = input_data.strip()
        normalized = cleaned.lower()
        tokens = normalized.split()
        result = [t for t in tokens if len(t) > 2]
        return result
