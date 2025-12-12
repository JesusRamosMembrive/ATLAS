"""True Negative Test Cases - Should NOT be detected as clones."""

# CASE 1: Similar structure but completely different logic
def add_numbers(a, b):
    """Add two numbers."""
    result = a + b
    return result

def multiply_numbers(a, b):
    """Multiply two numbers."""
    result = a * b
    return result


# CASE 2: Same variable names but different algorithms
def sort_ascending(items):
    """Sort items ascending."""
    sorted_items = sorted(items)
    return sorted_items

def sort_descending(items):
    """Sort items descending."""
    sorted_items = sorted(items, reverse=True)
    return sorted_items


# CASE 3: Common patterns but distinct implementations
def process_list_filter(data):
    """Filter-based processing."""
    result = []
    for item in data:
        if item > 0:
            result.append(item)
    return result

def process_list_transform(data):
    """Transform-based processing."""
    result = []
    for item in data:
        transformed = item * 2
        result.append(transformed)
    return result


# CASE 4: Same interface, different body
class ReaderA:
    def read(self, path):
        with open(path, 'r') as f:
            return f.read()

class ReaderB:
    def read(self, path):
        import json
        with open(path, 'r') as f:
            return json.load(f)


# CASE 5: Superficially similar, fundamentally different
def calculate_area_circle(radius):
    """Calculate circle area."""
    import math
    area = math.pi * radius * radius
    return area

def calculate_area_square(side):
    """Calculate square area."""
    area = side * side
    return area


# CASE 6: Short common patterns (should not trigger)
def get_name(obj):
    return obj.name

def get_value(obj):
    return obj.value

def get_id(obj):
    return obj.id


# CASE 7: Unique utility functions
def parse_date(date_str):
    """Parse date string to datetime."""
    from datetime import datetime
    return datetime.strptime(date_str, "%Y-%m-%d")

def format_currency(amount):
    """Format amount as currency."""
    return f"${amount:,.2f}"

def validate_email(email):
    """Basic email validation."""
    return "@" in email and "." in email
