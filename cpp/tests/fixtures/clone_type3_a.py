# Type-3 Clone Test Fixture A - Original version
# This file contains the original implementation

def process_data(items):
    """Process a list of items and return doubled positive values."""
    result = []
    for item in items:
        if item > 0:
            result.append(item * 2)
    return result


def calculate_statistics(numbers):
    """Calculate basic statistics for a list of numbers."""
    if not numbers:
        return None

    total = sum(numbers)
    count = len(numbers)
    average = total / count

    minimum = min(numbers)
    maximum = max(numbers)

    return {
        'sum': total,
        'count': count,
        'average': average,
        'min': minimum,
        'max': maximum
    }


def filter_and_transform(data, threshold):
    """Filter data above threshold and transform it."""
    filtered = []
    for value in data:
        if value > threshold:
            transformed = value * value
            filtered.append(transformed)
    return filtered
