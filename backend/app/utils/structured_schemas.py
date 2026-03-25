"""
Pydantic models for structured LLM output.

Used with Anthropic's messages.parse() for schema-constrained JSON generation.
These models define the exact shape of LLM responses, eliminating prompt-based
JSON hacks and post-hoc parsing.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ── Ontology generation schema ──


class OntologyAttribute(BaseModel):
    name: str = Field(description="Attribute name in snake_case (e.g. full_name, role)")
    type: str = Field(default="text", description="Attribute data type (text, number, etc.)")
    description: str = Field(description="Brief description of what this attribute represents")


class OntologyEntityType(BaseModel):
    name: str = Field(description="Entity type name in PascalCase (e.g. GovernmentLeader)")
    description: str = Field(description="Brief description, max 100 characters")
    attributes: List[OntologyAttribute] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list, description="2-3 example entities of this type")


class OntologySourceTarget(BaseModel):
    source: str = Field(description="Source entity type name")
    target: str = Field(description="Target entity type name")


class OntologyEdgeType(BaseModel):
    name: str = Field(description="Relationship type name in UPPER_SNAKE_CASE (e.g. ALLIES_WITH)")
    description: str = Field(description="Brief description, max 100 characters")
    source_targets: List[OntologySourceTarget] = Field(default_factory=list)
    attributes: List[OntologyAttribute] = Field(default_factory=list)


class OntologyResult(BaseModel):
    """Complete ontology definition for a MiroFish simulation."""

    entity_types: List[OntologyEntityType] = Field(
        description="Exactly 10 entity types: 8 specific + Person and Organization fallbacks"
    )
    edge_types: List[OntologyEdgeType] = Field(
        description="Relationship types connecting the entity types"
    )
    analysis_summary: str = Field(
        default="",
        description="Brief analysis summary of the text content and how entities relate"
    )
