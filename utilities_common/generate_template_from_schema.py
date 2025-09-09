#!/usr/bin/env python
"""
Generate error_report_template.json from error_report_schema.json.
This script reads the JSON schema and generates a template with default values.

Usage:
    python generate_template_from_schema.py

This script should be run whenever the schema is updated to ensure the template
stays in sync with the schema defaults. The generated template is used as the
default structure for error reports when the error_reporter module is initialized.

Note: This script is for development/maintenance only and is not needed at runtime.
The generated template file is included in the package distribution.
"""

import json
import os


def get_default_value(schema_property):
    """Get the default value for a property from its schema definition."""
    if 'default' in schema_property:
        return schema_property['default']
    
    prop_type = schema_property.get('type')
    if prop_type == 'string':
        return ""
    elif prop_type == 'boolean':
        return False
    elif prop_type == 'integer':
        return 0
    elif prop_type == 'number':
        return 0
    elif prop_type == 'array':
        # For errors array, include a default timeout error
        if 'items' in schema_property:
            items_schema = schema_property['items']
            if items_schema.get('type') == 'object':
                # Check if this is the errors array by looking at required properties
                required = items_schema.get('required', [])
                if 'name' in required and 'message' in required:
                    return [{
                        "name": "TIMEOUT",
                        "message": "Operation timed out or system crashed"
                    }]
        return []
    elif prop_type == 'object':
        return generate_object_from_schema(schema_property)
    return None


def generate_object_from_schema(schema):
    """Generate an object from a schema definition."""
    if 'properties' not in schema:
        return {}
    
    result = {}
    properties = schema['properties']
    
    for prop_name, prop_schema in properties.items():
        result[prop_name] = get_default_value(prop_schema)
    
    return result


def generate_template_from_schema(schema_path, output_path):
    """Generate a template JSON file from a JSON schema."""
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    
    # Generate the template from the root schema
    template = generate_object_from_schema(schema)
    
    # Write the template to file
    with open(output_path, 'w') as f:
        json.dump(template, f, indent=2)
    
    print("Generated template: {}".format(output_path))
    print("Template content:")
    print(json.dumps(template, indent=2))


def main():
    """Main function to generate template from schema."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(script_dir, 'error_report_schema.json')
    output_path = os.path.join(script_dir, 'error_report_template.json')
    
    if not os.path.exists(schema_path):
        print("Error: Schema file not found at {}".format(schema_path))
        return 1
    
    generate_template_from_schema(schema_path, output_path)
    return 0


if __name__ == '__main__':
    exit(main())