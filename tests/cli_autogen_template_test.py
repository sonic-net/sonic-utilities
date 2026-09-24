import os

from jinja2 import Environment, FileSystemLoader


TEST_PATH = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_PATH = os.path.join(
    TEST_PATH, "..", "sonic-utilities-data", "templates", "sonic-cli-gen"
)


def test_gen_click_options_escapes_multiline_help():
    env = Environment(loader=FileSystemLoader(TEMPLATES_PATH))
    template = env.get_template("config.py.j2")
    rendered = template.module.gen_click_options(
        [
            {
                "name": "buffer_model",
                "description": "line1\nline2 \"quoted\"",
                "is-mandatory": True,
            }
        ]
    )

    assert 'help="line1\\nline2 \\"quoted\\"[mandatory]"' in rendered
