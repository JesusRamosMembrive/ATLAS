#!/usr/bin/env python3
"""Generate stress test files for similarity detector."""
import os
import random
import string

def generate_function(name, num_lines=10):
    """Generate a random function."""
    lines = [f"def {name}(arg1, arg2, arg3):"]
    lines.append(f'    """Docstring for {name}."""')

    for i in range(num_lines - 4):
        var = f"var_{i}"
        op = random.choice(["+", "-", "*", "/", "//", "%"])
        val = random.randint(1, 1000)
        lines.append(f"    {var} = arg1 {op} {val}")

    lines.append("    return var_0")
    lines.append("")
    return "\n".join(lines)

def generate_class(name, num_methods=5):
    """Generate a random class."""
    lines = [f"class {name}:"]
    lines.append(f'    """Class {name} documentation."""')
    lines.append("")

    for i in range(num_methods):
        method_name = f"method_{i}"
        lines.append(f"    def {method_name}(self, x, y):")
        lines.append(f'        """Method {method_name}."""')
        lines.append(f"        result = x + y + {i}")
        lines.append("        return result")
        lines.append("")

    return "\n".join(lines)

def generate_large_file(filename, num_functions=50, num_classes=10):
    """Generate a large Python file."""
    content = ['"""Auto-generated stress test file."""', "import os", "import sys", "import random", ""]

    # Generate functions
    for i in range(num_functions):
        content.append(generate_function(f"function_{i}", random.randint(8, 20)))

    # Generate classes
    for i in range(num_classes):
        content.append(generate_class(f"TestClass_{i}", random.randint(3, 8)))

    with open(filename, "w") as f:
        f.write("\n".join(content))

def generate_duplicate_file(source, dest):
    """Create a file with some duplicated functions."""
    with open(source, "r") as f:
        content = f.read()

    # Modify some variable names to create Type-2 clones
    modified = content.replace("arg1", "param1").replace("arg2", "param2")
    modified = modified.replace("var_", "temp_")

    with open(dest, "w") as f:
        f.write(modified)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Generate 5 large files (~1000 lines each)
    for i in range(5):
        filename = os.path.join(base_dir, f"large_file_{i}.py")
        generate_large_file(filename, num_functions=40, num_classes=8)
        print(f"Generated {filename}")

    # Create duplicates with modifications
    generate_duplicate_file(
        os.path.join(base_dir, "large_file_0.py"),
        os.path.join(base_dir, "large_file_0_dup.py")
    )
    print("Generated duplicate file")

    # Generate many small files
    small_dir = os.path.join(base_dir, "many_files")
    os.makedirs(small_dir, exist_ok=True)

    for i in range(50):
        filename = os.path.join(small_dir, f"module_{i}.py")
        with open(filename, "w") as f:
            f.write(f'"""Module {i}."""\n\n')
            f.write(generate_function(f"func_{i}", 15))
            if i % 5 == 0:
                # Every 5th file has a clone
                f.write(generate_function("common_function", 10))
        print(f"Generated {filename}")

    print("\nStress test files generated successfully!")
