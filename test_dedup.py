
import unittest
from code_map.terminal.pty_shell import PTYShell

class TestPTYShellDeduplication(unittest.TestCase):
    def setUp(self):
        self.shell = PTYShell()

    def test_deduplication(self):
        """Test that repeated lines are filtered"""
        text = "Line 1\nLine 1\nLine 2\nLine 1"
        out = self.shell._process_output(text)
        # Expected: Line 1, Line 2, Line 1 (because Line 1 is different from Line 2)
        # Wait, my logic is: if clean_line == last_printed_line: continue
        # So:
        # 1. "Line 1" -> printed, last="Line 1"
        # 2. "Line 1" -> skipped
        # 3. "Line 2" -> printed, last="Line 2"
        # 4. "Line 1" -> printed, last="Line 1"
        expected = "Line 1\r\nLine 2\r\nLine 1\r\n"
        self.assertEqual(out, expected)

    def test_prompt_repetition(self):
        """Test prompt repetition scenario"""
        prompt = "> responde solo pong"
        text = f"{prompt}\n{prompt}\n{prompt}"
        out = self.shell._process_output(text)
        expected = f"{prompt}\r\n"
        self.assertEqual(out, expected)

    def test_empty_lines(self):
        """Test that empty lines are skipped"""
        text = "Line 1\n\nLine 2"
        out = self.shell._process_output(text)
        expected = "Line 1\r\nLine 2\r\n"
        self.assertEqual(out, expected)

if __name__ == '__main__':
    unittest.main()
