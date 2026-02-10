import unittest
import json
from core.safety import validate_imports, run_in_sandbox

class TestImportValidation(unittest.TestCase):
    def test_allowed_imports(self):
        code = """
import numpy as np
import math
from datetime import datetime
import json
"""
        is_valid, error = validate_imports(code)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_disallowed_import(self):
        code = "import requests"
        is_valid, error = validate_imports(code)
        self.assertFalse(is_valid)
        error_json = json.loads(error)
        self.assertEqual(error_json['status'], 'dependency_error')
        self.assertEqual(error_json['missing_lib'], 'requests')

    def test_disallowed_from_import(self):
        code = "from sklearn import metrics"
        is_valid, error = validate_imports(code)
        self.assertFalse(is_valid)
        error_json = json.loads(error)
        self.assertEqual(error_json['missing_lib'], 'sklearn')

    def test_run_in_sandbox_integration(self):
        code = "import requests\nprint('hello')"
        result = run_in_sandbox(code)
        # Should return JSON string directly
        self.assertTrue(result.startswith('{'))
        error_json = json.loads(result)
        self.assertEqual(error_json['status'], 'dependency_error')

    def test_syntax_error(self):
        code = "import (" # Invalid syntax
        is_valid, error = validate_imports(code)
        self.assertFalse(is_valid)
        error_json = json.loads(error)
        self.assertEqual(error_json['missing_lib'], 'syntax_error')

if __name__ == '__main__':
    print("--- Testing Import Validation ---")
    unittest.main()
