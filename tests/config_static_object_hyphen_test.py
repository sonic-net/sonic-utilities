import jinja2


def test_function_naming_fragment():
    """
    Test the specific template fragment that generates function names
    """

    # Test the exact template fragment we modified
    template_fragment = '''
{%- macro pythonize(attrs) -%}
{{ attrs|map(attribute="name")|map("lower")|map("replace", "-", "_")|join(", ") }}
{%- endmacro %}
def {{ table.name }}_{{ object.name }}_{{ attr.name|lower|replace("-", "_") }}(db, {{ pythonize([attr]) }}):
    """ {{ attr.description }} """
'''

    # Create template from string
    template = jinja2.Template(template_fragment)

    # Test data
    test_context = {
        'table': {'name': 'SAMPLE_DATA'},
        'object': {'name': 'local'},
        'attr': {
            'name': 'attribute-with-hyphen',
            'description': 'Attribute with hyphen'
        }
    }

    # Render
    result = template.render(**test_context)

    # Verify function name conversion
    assert "def SAMPLE_DATA_local_attribute_with_hyphen(" in result
    assert "attribute_with_hyphen" in result  # parameter name

    print("✅ Config Template fragment test passed!")
    print("Generated function signature:")
    print(result.split('\n')[3])  # Print function definition line


def test_edge_cases():
    """Test edge cases for function naming"""

    template_fragment = '{{ attr.name|lower|replace("-", "_") }}'
    template = jinja2.Template(template_fragment)

    test_cases = [
        ('single-hyphen', 'single_hyphen'),
        ('multi-hyphen-test', 'multi_hyphen_test'), 
        ('no_hyphens', 'no_hyphens'),
        ('Mixed-Case-Hyphens', 'mixed_case_hyphens'),
        ('trailing-', 'trailing_'),
        ('-leading', '_leading'),
        ('consecutive--hyphens', 'consecutive__hyphens')
    ]

    for input_name, expected_output in test_cases:
        result = template.render(attr={'name': input_name})
        assert result == expected_output, f"Failed for {input_name}: got {result}, expected {expected_output}"

    print("✅ Edge case tests passed!")


if __name__ == "__main__":
    test_function_naming_fragment()
    test_edge_cases()
