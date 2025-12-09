def unique_function(x, y, z):
    """This is a completely unique function."""
    result = x * y + z
    for i in range(10):
        result += i * x
    return result
