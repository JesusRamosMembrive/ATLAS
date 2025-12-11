import ast
import unittest
from code_map.analyzer import calculate_complexity


class TestComplexity(unittest.TestCase):
    def test_basic_complexity(self):
        code = """
def foo():
    pass
"""
        node = ast.parse(code).body[0]
        self.assertEqual(calculate_complexity(node), 1)

    def test_branching_complexity(self):
        code = """
def foo(x):
    if x:
        return 1
    else:
        return 0
"""
        node = ast.parse(code).body[0]
        self.assertEqual(calculate_complexity(node), 2)

    def test_loop_complexity(self):
        code = """
def foo():
    for i in range(10):
        if i % 2 == 0:
            print(i)
"""
        node = ast.parse(code).body[0]
        self.assertEqual(calculate_complexity(node), 3)  # 1 (base) + 1 (for) + 1 (if)

    def test_while_complexity(self):
        code = """
def foo():
    while True:
        break
"""
        node = ast.parse(code).body[0]
        self.assertEqual(calculate_complexity(node), 2)


if __name__ == "__main__":
    unittest.main()
