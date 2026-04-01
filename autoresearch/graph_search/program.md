# AutoResearch: Graph Search & Retrieval Optimization

## Objective

Optimize the graph search strategy in `strategies/search_strategy.py` to
maximize retrieval quality when searching a knowledge graph for research
questions. The strategy controls keyword matching, scoring, ranking, and
query expansion.

## How It Works

1. Read this file for research directions.
2. Modify **only** `strategies/search_strategy.py`.
3. Run `python3 train.py` — searches a static graph (25 nodes, 22 edges)
   for 10 research questions and scores against gold-standard results.
4. Score is appended to `results/history.jsonl`.
5. Decide keep/revert based on the metric.

**No LLM calls needed.** Each run takes <1 second.

## Metric: search_score

```
search_score = 0.30 * edge_recall
             + 0.20 * node_recall
             + 0.30 * keyword_recall
             + 0.20 * mrr
```

- **edge_recall**: fraction of gold-standard edges found in results
- **node_recall**: fraction of gold nodes appearing as endpoints in results
- **keyword_recall**: fraction of gold keywords found in retrieved facts
- **mrr**: mean reciprocal rank of gold edges in result ranking

## Test Queries

10 queries across 3 difficulty levels:
- **easy** (3): Direct entity/relationship lookups
- **medium** (3): Multi-entity queries requiring broader matching
- **hard** (4): Cross-topic, pattern-based, abstract queries

Hard queries are where the biggest gains are possible — they require
matching across different topics and finding implicit connections.

## Research Directions

### Round 1-5: Scoring improvements
- The baseline `match_score` awards 100 for exact query match, 10 per keyword
- Try TF-IDF-like weighting (rare keywords score higher)
- Try partial/substring keyword matching
- Try n-gram matching (bigrams from the query)
- Test word stemming (simple suffix stripping: "regulates" -> "regulat")

### Round 6-10: Query expansion
- Expand synonyms (e.g., "oppose" matches "criticized", "protested")
- Extract entity names from the query and boost their matches
- Try matching relationship type names (OPPOSES, SUPPORTS, etc.)
- Build keyword variations (plural/singular, verb forms)

### Round 11-15: Advanced ranking
- Boost edges where both source and target match query keywords
- Implement relevance feedback: facts mentioning more gold-relevant
  entities should rank higher
- Try inverse document frequency across the graph
- Test edge-type-aware scoring (OPPOSES edges for opposition queries)

### Round 16-20: Node integration
- Boost edges connected to nodes whose summaries match the query
- Use node labels (entity types) as scoring signals
- Implement 2-hop scoring: boost edges that share a node with a
  high-scoring edge

### Round 21+: Sub-query prompt optimization
- Improve the SUB_QUERY_SYSTEM_PROMPT for better decomposition
- Test different decomposition strategies (entity-centric vs topic-centric)
- Note: sub-query prompt changes only matter when used with LLM;
  the train.py loop tests the scoring functions directly

## Constraints

- **Only modify** `strategies/search_strategy.py`
- No external dependencies (stdlib only)
- Functions must keep their signatures (train.py calls them)
- Keep module under 400 lines

## Architecture

The strategy module exports:
1. `SUB_QUERY_SYSTEM_PROMPT` — system prompt for LLM query decomposition
2. `SUB_QUERY_USER_TEMPLATE` — user prompt template
3. `match_score(text, query, keywords)` — relevance scoring
4. `tokenize_query(query)` — query → keywords
5. `rank_edges(edges, query, keywords, limit)` — score and rank edges
6. `rank_nodes(nodes, query, keywords, limit)` — score and rank nodes
7. `deduplicate_facts(facts)` — remove duplicates
