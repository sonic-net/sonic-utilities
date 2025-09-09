#!/usr/bin/env python

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch

from utilities_common.generate_template_from_schema import (
    get_default_value,
    generate_object_from_schema,
    generate_template_from_schema,
    main
)

# Add the parent directory to the path to import the module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestGenerateTemplateFromSchema(unittest.TestCase):

    def test_get_default_value_with_explicit_default(self):
        """Test that explicit defaults are returned."""
        schema_prop = {"type": "string", "default": "test_value"}
        result = get_default_value(schema_prop)
        self.assertEqual(result, "test_value")

    def test_get_default_value_string_type(self):
        """Test default value for string type."""
        schema_prop = {"type": "string"}
        result = get_default_value(schema_prop)
        self.assertEqual(result, "")

    def test_get_default_value_boolean_type(self):
        """Test default value for boolean type."""
        schema_prop = {"type": "boolean"}
        result = get_default_value(schema_prop)
        self.assertEqual(result, False)

    def test_get_default_value_integer_type(self):
        """Test default value for integer type."""
        schema_prop = {"type": "integer"}
        result = get_default_value(schema_prop)
        self.assertEqual(result, 0)

    def test_get_default_value_number_type(self):
        """Test default value for number type."""
        schema_prop = {"type": "number"}
        result = get_default_value(schema_prop)
        self.assertEqual(result, 0)

    def test_get_default_value_array_type(self):
        """Test default value for array type."""
        schema_prop = {"type": "array"}
        result = get_default_value(schema_prop)
        self.assertEqual(result, [])

    def test_get_default_value_errors_array(self):
        """Test default value for errors array with specific structure."""
        schema_prop = {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "message"],
                "properties": {
                    "name": {"type": "string"},
                    "message": {"type": "string"}
                }
            }
        }
        result = get_default_value(schema_prop)
        expected = [{
            "name": "TIMEOUT",
            "message": "Operation timed out or system crashed"
        }]
        self.assertEqual(result, expected)

    def test_get_default_value_object_type(self):
        """Test default value for object type."""
        schema_prop = {
            "type": "object",
            "properties": {
                "field1": {"type": "string"},
                "field2": {"type": "boolean"}
            }
        }
        result = get_default_value(schema_prop)
        expected = {"field1": "", "field2": False}
        self.assertEqual(result, expected)

    def test_generate_object_from_schema_empty(self):
        """Test generating object from schema without properties."""
        schema = {"type": "object"}
        result = generate_object_from_schema(schema)
        self.assertEqual(result, {})

    def test_generate_object_from_schema_with_properties(self):
        """Test generating object from schema with properties."""
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "test"},
                "enabled": {"type": "boolean"},
                "count": {"type": "integer"}
            }
        }
        result = generate_object_from_schema(schema)
        expected = {
            "name": "test",
            "enabled": False,
            "count": 0
        }
        self.assertEqual(result, expected)

    def test_generate_template_from_schema_file_operations(self):
        """Test the complete template generation from file."""
        # Create a mock schema
        mock_schema = {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "object",
                    "properties": {
                        "version": {"type": "string", "default": "1.0.0"},
                        "status": {"type": "boolean", "default": True}
                    }
                }
            }
        }
        
        expected_template = {
            "summary": {
                "version": "1.0.0",
                "status": True
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as schema_file:
            json.dump(mock_schema, schema_file)
            schema_path = schema_file.name

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as template_file:
            template_path = template_file.name

        try:
            generate_template_from_schema(schema_path, template_path)
            
            # Read the generated template
            with open(template_path, 'r') as f:
                result = json.load(f)
            
            self.assertEqual(result, expected_template)
        finally:
            # Clean up
            os.unlink(schema_path)
            os.unlink(template_path)

    @patch('utilities_common.generate_template_from_schema.generate_template_from_schema')
    @patch('os.path.exists')
    def test_main_success(self, mock_exists, mock_generate):
        """Test main function success path."""
        mock_exists.return_value = True
        mock_generate.return_value = None
        
        result = main()
        self.assertEqual(result, 0)
        mock_generate.assert_called_once()

    @patch('os.path.exists')
    def test_main_schema_not_found(self, mock_exists):
        """Test main function when schema file doesn't exist."""
        mock_exists.return_value = False
        
        result = main()
        self.assertEqual(result, 1)

    @patch('builtins.print')
    @patch('utilities_common.generate_template_from_schema.generate_template_from_schema')
    @patch('os.path.exists')
    def test_main_prints_output(self, mock_exists, mock_generate, mock_print):
        """Test that main function prints expected output."""
        mock_exists.return_value = True
        mock_generate.return_value = None
        
        main()
        # Verify that generate_template_from_schema was called
        mock_generate.assert_called_once()


if __name__ == '__main__':
    unittest.main()