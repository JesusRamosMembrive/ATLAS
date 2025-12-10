# Test file for Type-2 clone detection (renamed variables)
# Same structure as clone_type2_b.py but different names

def calculate_sum(numbers, multiplier):
    """Calculate sum of numbers with multiplier."""
    total = 0
    for num in numbers:
        if num > 0:
            total += num * multiplier
    return total


def filter_items(items, threshold):
    """Filter items above threshold."""
    result = []
    for item in items:
        if item.value > threshold:
            result.append(item)
    return result


def transform_data(input_data, transformer):
    """Transform data using transformer function."""
    output = []
    for element in input_data:
        transformed = transformer(element)
        output.append(transformed)
    return output
