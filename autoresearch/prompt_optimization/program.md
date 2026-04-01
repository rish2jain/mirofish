# AutoResearch: Entity Extraction Prompt Optimization

## Objective

Optimize the entity extraction prompt in `prompts/entity_extraction.py` to maximize
precision and recall of entities and relationships extracted from text documents.

## How It Works

1. You read this file for research directions and context.
2. You modify **only** `prompts/entity_extraction.py` (the system prompt and user template).
3. Run `uv run python train.py` — it extracts entities from 3 eval documents using
   the current prompt, scores the output against gold-standard labels, and prints a
   single composite metric: **extraction_score** (0.0 to 1.0).
4. The score is appended to `results/history.jsonl`.
5. Decide whether to keep or revert the change based on the metric.
6. Repeat.

## Metric: extraction_score

```
extraction_score = 0.4 * entity_precision
                 + 0.3 * entity_recall
                 + 0.2 * relationship_f1
                 + 0.1 * valid_json_rate
```

- **entity_precision**: fraction of extracted entities that match a gold entity (fuzzy name match)
- **entity_recall**: fraction of gold entities found in extracted output
- **relationship_f1**: F1 of (source, target, type) triples vs gold relationships
- **valid_json_rate**: fraction of LLM responses that parse as valid JSON on first try

## Research Directions (try these)

### Round 1-5: Structural improvements
- Add explicit chain-of-thought: "First list all entities you see, then identify relationships"
- Add a "common mistakes" section warning about typical errors
- Try numbered output format vs current JSON schema
- Reduce prompt verbosity — shorter prompts often outperform longer ones

### Round 6-10: Few-shot examples
- Add 1-2 concrete extraction examples to the prompt
- Vary example complexity (simple doc vs complex doc)
- Test whether examples help more for entities or relationships

### Round 11-15: Schema enforcement
- Add JSON schema inline (not just format description)
- Test "output a JSON array of entities, then separately output relationships" vs single object
- Try XML-tagged sections: `<entities>...</entities><relationships>...</relationships>`

### Round 16-20: Domain adaptation
- Test domain-specific entity type hints in the prompt
- Add "entity type priority" guidance (prefer specific types over generic)
- Test bilingual prompts (English instructions + Chinese entity support)

### Round 21+: Ablation & refinement
- Remove parts of the prompt to measure their contribution
- Combine the best ideas from previous rounds
- Fine-tune temperature and max_tokens alongside prompt changes

## Constraints

- **Only modify** `prompts/entity_extraction.py`
- **Budget**: Each `train.py` run takes ~60 seconds (3 documents x ~20s per LLM call)
- **No changes** to `train.py`, `prepare.py`, or `eval_data/`
- Keep the prompt under 2000 tokens (measured by `train.py`)

## Current Best Score

Check `results/history.jsonl` for the latest scores. If no history exists, the
baseline is whatever the first run produces.
