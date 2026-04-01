"""Generated ontology Python source stays valid for arbitrary description text."""

from unittest.mock import MagicMock

import pytest

from app.services.ontology_generator import OntologyGenerator


@pytest.fixture
def generator_no_llm():
    return OntologyGenerator(llm_client=MagicMock())


def test_generate_python_code_escapes_field_descriptions(generator_no_llm):
    ontology = {
        "entity_types": [
            {
                "name": "FooEnt",
                "description": "entity doc",
                "attributes": [
                    {
                        "name": "risky",
                        "description": 'He said "hi"\nline2\\\t',
                    }
                ],
            }
        ],
        "edge_types": [
            {
                "name": "LINKS_TO",
                "description": "rel",
                "source_targets": [],
                "attributes": [
                    {"name": "meta", "description": "a'b\"c\n"},
                ],
            }
        ],
    }
    code = generator_no_llm.generate_python_code(ontology)
    compile(code, "<ontology_gen>", "exec")
    assert "description=" in code
    assert 'Field(' in code
