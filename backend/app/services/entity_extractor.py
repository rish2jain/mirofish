"""
LLM-based Entity and Relationship Extractor
Uses the configured LLM to replace the old managed extraction pipeline.
Uses the configured LLM to extract entities and relationships from text chunks.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set

from .graph_storage import GraphStorage
from ..config import Config
from ..utils.llm_cache import LLMResponseCache
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('mirofish.entity_extractor')

EXTRACTION_SYSTEM_PROMPT = """You are a knowledge graph entity extraction expert. Your task is to extract entities and relationships from text based on a given ontology schema.

## Rules
1. Extract ONLY entities whose types match the provided entity types
2. Extract ONLY relationships whose types match the provided relationship types
3. Entity names should be proper nouns or specific identifiers found in the text
4. Each relationship must reference entities that exist in your extraction
5. Be thorough but precise - extract all relevant entities and relationships mentioned in the text
6. For each entity, provide a brief summary based on context in the text
7. For each relationship, provide a fact statement describing the relationship

## Output Format
Return valid JSON with this exact structure:
{
  "entities": [
    {
      "name": "Entity Name",
      "type": "EntityType",
      "summary": "Brief description based on the text context"
    }
  ],
  "relationships": [
    {
      "source": "Source Entity Name",
      "target": "Target Entity Name",
      "type": "relationship_type",
      "fact": "A sentence describing this relationship"
    }
  ]
}

If no entities or relationships are found, return:
{"entities": [], "relationships": []}
"""


class EntityExtractor:
    """
    Extracts entities and relationships from text using LLM.
    Designed to replace the old managed automatic entity extraction pipeline.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        storage: Optional[GraphStorage] = None,
        cache: Optional[LLMResponseCache] = None,
    ):
        self.llm = llm_client or LLMClient()
        self.storage = storage
        self._cache = cache if cache is not None else (
            LLMResponseCache() if getattr(Config, "LLM_CACHE_ENABLED", False) else None
        )

    def extract(
        self,
        text: str,
        ontology: Dict[str, Any],
        max_text_length: int = 8000
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from a text chunk.

        Args:
            text: Text to extract from
            ontology: Ontology definition with entity_types and edge_types
            max_text_length: Maximum text length to send to LLM

        Returns:
            Dict with 'entities' and 'relationships' lists
        """
        if not text or not text.strip():
            return {"entities": [], "relationships": []}

        # Truncate if needed
        if len(text) > max_text_length:
            text = text[:max_text_length] + "\n...[truncated]"

        # Build ontology description
        entity_types_desc = self._format_entity_types(ontology)
        edge_types_desc = self._format_edge_types(ontology)

        user_message = f"""## Ontology Schema

### Entity Types
{entity_types_desc}

### Relationship Types
{edge_types_desc}

## Text to Extract From
{text}

Extract all entities and relationships from the text above that match the ontology schema. Return valid JSON only."""

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # Check cache first
        if self._cache is not None:
            cached = self._cache.get(
                messages=messages,
                model=self.llm.model or "",
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            if cached is not None:
                try:
                    result = json.loads(cached)
                    entities = result.get("entities", [])
                    relationships = result.get("relationships", [])
                    logger.debug(
                        "Cache hit: %d entities, %d relationships",
                        len(entities), len(relationships),
                    )
                    return {"entities": entities, "relationships": relationships}
                except (json.JSONDecodeError, TypeError):
                    pass  # Stale/corrupt cache entry — fall through to LLM

        # Side-effect only: estimate_call_cost logs DEBUG / WARN on threshold; return unused.
        self.llm.estimate_call_cost(messages, expected_completion_tokens=2000)

        try:
            result = self.llm.chat_json(
                messages=messages,
                temperature=0.2,
                max_tokens=4096,
            )

            entities = result.get("entities", [])
            relationships = result.get("relationships", [])

            # Store in cache
            if self._cache is not None:
                self._cache.put(
                    messages=messages,
                    model=self.llm.model or "",
                    temperature=0.2,
                    response=json.dumps(result, ensure_ascii=False),
                    response_format={"type": "json_object"},
                )

            logger.debug(f"Extracted {len(entities)} entities, {len(relationships)} relationships")
            return {"entities": entities, "relationships": relationships}

        except Exception as e:
            logger.warning(f"Entity extraction failed for chunk: {str(e)[:200]}")
            return {"entities": [], "relationships": []}

    @staticmethod
    def _merge_entities(
        all_entities: Dict[str, Dict],
        entities: List[Dict],
    ) -> None:
        """Merge extracted entities into the accumulator (deduplicate by name)."""
        for entity in entities:
            name = entity.get("name", "").strip()
            if not name:
                continue
            key = name.lower()
            if key in all_entities:
                existing = all_entities[key]
                if len(entity.get("summary", "")) > len(existing.get("summary", "")):
                    existing["summary"] = entity["summary"]
                if entity.get("type") and entity["type"] != existing.get("type"):
                    existing.setdefault("additional_types", []).append(entity["type"])
            else:
                all_entities[key] = entity

    @staticmethod
    def _merge_relationships(
        all_relationships: List[Dict],
        relationships: List[Dict],
        seen_keys: Optional[Set[str]] = None,
    ) -> None:
        """Merge extracted relationships into the accumulator (deduplicate).

        Deduplication key: ``f"{source}|{target}|{type}"`` with each part
        ``strip()``'d and ``lower()``'d. Pass a shared ``seen_keys=set()`` across
        multiple calls to avoid rebuilding the set from ``all_relationships``
        each time.
        """
        if seen_keys is None:
            seen_keys = set()
            for r in all_relationships:
                s = r.get("source", "").strip().lower()
                t = r.get("target", "").strip().lower()
                rt = r.get("type", "").strip().lower()
                if s and t:
                    seen_keys.add(f"{s}|{t}|{rt}")

        for rel in relationships:
            source = rel.get("source", "").strip().lower()
            target = rel.get("target", "").strip().lower()
            rel_type = rel.get("type", "").strip().lower()
            if not source or not target:
                continue
            key = f"{source}|{target}|{rel_type}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            all_relationships.append(rel)

    def extract_batch(
        self,
        chunks: List[str],
        ontology: Dict[str, Any],
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from multiple text chunks,
        merging results across chunks.

        When ``PARALLEL_ENTITY_EXTRACTION`` is enabled (default), chunks are
        processed concurrently using a thread pool for 3-5x speedup.

        Args:
            chunks: List of text chunks
            ontology: Ontology definition
            progress_callback: Optional callback(message, progress_ratio)

        Returns:
            Merged dict with 'entities' and 'relationships'
        """
        all_entities: Dict[str, Dict] = {}
        all_relationships: List[Dict] = []
        seen_rel_keys: Set[str] = set()
        total = len(chunks)

        use_parallel = getattr(Config, "PARALLEL_ENTITY_EXTRACTION", True)
        max_workers = getattr(Config, "PARALLEL_ENTITY_EXTRACTION_WORKERS", 4)

        if use_parallel and total > 1:
            return self._extract_batch_parallel(
                chunks, ontology, progress_callback,
                all_entities, all_relationships, max_workers, seen_rel_keys,
            )

        # Sequential fallback
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(
                    f"Extracting entities from chunk {i+1}/{total}...",
                    (i + 1) / total,
                )
            result = self.extract(chunk, ontology)
            self._merge_entities(all_entities, result.get("entities", []))
            self._merge_relationships(
                all_relationships,
                result.get("relationships", []),
                seen_rel_keys,
            )

        logger.info(
            "Batch extraction complete: %d unique entities, "
            "%d unique relationships from %d chunks",
            len(all_entities), len(all_relationships), total,
        )
        return {
            "entities": list(all_entities.values()),
            "relationships": all_relationships,
        }

    def _extract_batch_parallel(
        self,
        chunks: List[str],
        ontology: Dict[str, Any],
        progress_callback,
        all_entities: Dict[str, Dict],
        all_relationships: List[Dict],
        max_workers: int,
        seen_rel_keys: Set[str],
    ) -> Dict[str, Any]:
        """Run extraction across chunks using a thread pool."""
        total = len(chunks)
        completed = 0

        logger.info(
            "Parallel entity extraction: %d chunks, %d workers",
            total, max_workers,
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(self.extract, chunk, ontology): i
                for i, chunk in enumerate(chunks)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                completed += 1

                if progress_callback:
                    progress_callback(
                        f"Extracting entities from chunk {completed}/{total}...",
                        completed / total,
                    )

                try:
                    result = future.result()
                except Exception as exc:
                    logger.warning(
                        "Parallel extraction failed for chunk %d: %s",
                        idx, str(exc)[:200],
                    )
                    continue

                self._merge_entities(all_entities, result.get("entities", []))
                self._merge_relationships(
                    all_relationships,
                    result.get("relationships", []),
                    seen_rel_keys,
                )

        logger.info(
            "Parallel batch extraction complete: %d unique entities, "
            "%d unique relationships from %d chunks",
            len(all_entities), len(all_relationships), total,
        )
        return {
            "entities": list(all_entities.values()),
            "relationships": all_relationships,
        }

    def _format_entity_types(self, ontology: Dict[str, Any]) -> str:
        """Format entity types for the prompt"""
        lines = []
        for et in ontology.get("entity_types", []):
            name = et.get("name", "Unknown")
            desc = et.get("description", "")
            attrs = et.get("attributes", [])
            attr_names = [a.get("name", "") for a in attrs]
            line = f"- **{name}**: {desc}"
            if attr_names:
                line += f" (attributes: {', '.join(attr_names)})"
            lines.append(line)
        return "\n".join(lines) if lines else "No specific entity types defined."

    def _format_edge_types(self, ontology: Dict[str, Any]) -> str:
        """Format edge types for the prompt"""
        lines = []
        for et in ontology.get("edge_types", []):
            name = et.get("name", "Unknown")
            desc = et.get("description", "")
            sources = []
            for st in et.get("source_targets", []):
                sources.append(f"{st.get('source', '?')} -> {st.get('target', '?')}")
            line = f"- **{name}**: {desc}"
            if sources:
                line += f" ({', '.join(sources)})"
            lines.append(line)
        return "\n".join(lines) if lines else "No specific relationship types defined."
