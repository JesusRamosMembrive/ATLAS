# Type-3 Clone Test Fixture B - Modified version with gaps
# This file contains modified implementations (~70-80% similar)

def process_data(items):
    """Process a list of items and return doubled positive values with total."""
    result = []
    total = 0  # Added line
    for item in items:
        if item > 0:
            value = item * 2  # Modified: extracted to variable
            result.append(value)
            total += value  # Added line
    return result, total  # Modified: return tuple


def calculate_statistics(numbers):
    """Calculate basic statistics for a list of numbers with variance."""
    if not numbers:
        return None

    total = sum(numbers)
    count = len(numbers)
    average = total / count

    minimum = min(numbers)
    maximum = max(numbers)

    # Added: variance calculation
    variance = sum((x - average) ** 2 for x in numbers) / count

    return {
        'sum': total,
        'count': count,
        'average': average,
        'min': minimum,
        'max': maximum,
        'variance': variance  # Added field
    }


def filter_and_transform(data, threshold):
    """Filter data above threshold and transform it with logging."""
    filtered = []
    skipped = 0  # Added: tracking skipped items
    for value in data:
        if value > threshold:
            transformed = value * value
            filtered.append(transformed)
        else:
            skipped += 1  # Added: count skipped
    print(f"Skipped {skipped} items")  # Added: logging
    return filtered
