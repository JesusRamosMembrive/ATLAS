# Test file for Type-2 clone detection (renamed variables)
# Same structure as clone_type2_a.py but different names

def compute_total(values, factor):
    """Calculate sum of values with factor."""
    result = 0
    for val in values:
        if val > 0:
            result += val * factor
    return result


def select_elements(elements, limit):
    """Filter elements above limit."""
    filtered = []
    for elem in elements:
        if elem.value > limit:
            filtered.append(elem)
    return filtered


def process_records(source_data, processor):
    """Transform records using processor function."""
    results = []
    for record in source_data:
        processed = processor(record)
        results.append(processed)
    return results
