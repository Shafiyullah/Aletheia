import unittest
from core.safety import static_analysis_check, SecurityViolationException

class TestASTSecurity(unittest.TestCase):
    def test_safe_code(self):
        code = "print('Hello World')"
        try:
            static_analysis_check(code)
        except SecurityViolationException:
            self.fail("Safe code raised SecurityViolationException")

    def test_import_os(self):
        code = "import os"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)

    def test_import_sys(self):
        code = "import sys"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)
    
    def test_from_os_import(self):
        code = "from os import path"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)

    def test_exec(self):
        code = "exec('print(1)')"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)

    def test_eval(self):
        code = "eval('1+1')"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)
            
    def test_open(self):
        code = "open('file.txt', 'w')"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)

    def test_subclasses(self):
        code = "[].__subclasses__()"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)

    def test_dunder_import_call(self):
        code = "__import__('os')"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)
            
    def test_obfuscated_import(self):
        # Spacing shouldn't matter for AST
        code = "import      os"
        with self.assertRaises(SecurityViolationException):
            static_analysis_check(code)

if __name__ == '__main__':
    print("--- Testing AST Security ---")
    unittest.main()
