"""
Graph search strategy — the ONLY file the autoresearch agent modifies.

Contains:
1. Sub-query decomposition prompt (for LLM-based query expansion)
2. Search scoring/ranking function (keyword matching heuristics)
3. Result ranking and deduplication logic
"""

from typing import Any, Dict, List, Set, Tuple
import re

# ---- Sub-query decomposition prompt ----
# Used to expand a research question into multiple graph search queries.

SUB_QUERY_SYSTEM_PROMPT = """You are a professional problem analysis expert. \
Your task is to decompose a complex question into multiple sub-questions \
that can be independently observed in a simulated world.

Requirements:
1. Each sub-question should be specific enough to find relevant agent \
behaviors or events in the simulated world
2. Sub-questions should cover different dimensions of the original \
question (e.g., who, what, why, how, when, where)
3. Sub-questions should be relevant to the simulation scenario
4. Return in JSON format: {"sub_queries": ["sub-question 1", ...]}"""

SUB_QUERY_USER_TEMPLATE = """Simulation requirement background:
{simulation_requirement}

{report_context_line}

Please decompose the following question into {max_queries} sub-questions:
{query}

Return the sub-question list in JSON format."""


# ---- Synonym / related-word expansion ----

SYNONYM_MAP: Dict[str, List[str]] = {
    "regulatory": ["regulates", "regulator", "regulation", "regulate", "regulat"],
    "regulation": ["regulates", "regulator", "regulatory", "regulate", "regulat"],
    "regulator": ["regulates", "regulation", "regulatory", "regulate", "regulat"],
    "executive": ["ceo", "president", "chief", "officer", "leader", "head"],
    "executives": ["ceo", "president", "chief", "officer", "leader", "head"],
    "bodies": ["agency", "commission", "body", "organization", "authority", "ftc"],
    "body": ["agency", "commission", "organization", "authority", "ftc"],
    "reaction": ["criticized", "praised", "opposed", "supported", "responded", "called"],
    "reactions": ["criticized", "praised", "opposed", "supported", "responded", "called"],
    "reacted": ["criticized", "praised", "opposed", "supported", "responded", "called"],
    "oppose": ["criticized", "opposes", "protested", "against"],
    "opposes": ["criticized", "oppose", "protested", "against"],
    "support": ["praised", "supports", "endorsed", "backed"],
    "supports": ["praised", "support", "endorsed", "backed"],
    "financial": ["market", "billion", "etf", "correction", "investment", "compliance", "demand", "nvidia"],
    "market": ["financial", "billion", "etf", "correction", "investment", "compliance", "demand", "nvidia"],
    "impact": ["effect", "consequence", "correction", "affect", "affected", "demand", "compliance", "opportunity"],
    "media": ["reuters", "bloomberg", "coverage", "published", "analysis", "news"],
    "coverage": ["published", "analysis", "report", "covered"],
    "investigation": ["investigate", "investigating", "investigated", "inquiry", "opened"],
    "investigate": ["investigation", "investigating", "investigated", "inquiry", "opened"],
    "breach": ["data breach", "exposed", "records", "security"],
    "acquisition": ["acquire", "acquired", "merger", "deal", "billion", "bid"],
    "deal": ["acquisition", "merger", "billion", "bid"],
    "merger": ["acquisition", "deal", "approve", "merge"],
    "approve": ["approval", "approved", "must approve"],
    "actions": ["action", "took", "opened", "requires", "applies", "must"],
    "involved": ["participated", "related", "connected", "took part"],
    "tech": ["technology", "ai", "company", "companies"],
    "developments": ["development", "act", "proposal", "regulation"],
    "recent": ["2026", "new", "latest", "announced"],
    "collaborative": ["collaborates", "collaboration", "hired", "acquisition", "partner"],
    "collaboration": ["collaborates", "collaborative", "hired", "acquisition", "partner"],
    "investigative": ["investigate", "investigation", "inquiry", "opened"],
    "relationships": ["relationship", "collaborates", "opposes", "supports", "regulates", "competes"],
    "dynamics": ["relationship", "collaborates", "opposes", "supports", "acquisition", "deal", "bid", "counter-bid"],
    "key": ["major", "important", "significant"],
    "patterns": ["pattern", "trend", "repeated"],
    "organizations": ["company", "ngo", "agency", "organization"],
    "corporate": ["company", "pfizer", "seagen", "merger", "acquisition"],
    "exist": ["found", "present", "identified"],
}

# Map query concepts to relevant edge relationship types
EDGE_TYPE_MAP: Dict[str, List[str]] = {
    "reaction": ["SUPPORTS", "OPPOSES"],
    "reactions": ["SUPPORTS", "OPPOSES"],
    "reacted": ["SUPPORTS", "OPPOSES"],
    "regulatory": ["REGULATES"],
    "regulation": ["REGULATES"],
    "regulator": ["REGULATES"],
    "oppose": ["OPPOSES"],
    "opposes": ["OPPOSES"],
    "opposition": ["OPPOSES"],
    "support": ["SUPPORTS"],
    "supports": ["SUPPORTS"],
    "collaborative": ["COLLABORATES_WITH"],
    "collaboration": ["COLLABORATES_WITH"],
    "investigative": ["COLLABORATES_WITH"],
    "investigation": ["REGULATES"],
    "media": ["REPORTS_ON"],
    "coverage": ["REPORTS_ON"],
    "compete": ["COMPETES_WITH"],
    "competitor": ["COMPETES_WITH"],
}

# Entity type hints: query concept -> node labels that should be considered relevant
ENTITY_TYPE_MAP: Dict[str, List[str]] = {
    "regulatory": ["GovernmentAgency"],
    "regulator": ["GovernmentAgency"],
    "regulation": ["GovernmentAgency"],
    "bodies": ["GovernmentAgency"],
    "body": ["GovernmentAgency"],
    "executive": ["Executive"],
    "executives": ["Executive"],
    "ceo": ["Executive"],
    "president": ["Executive"],
    "media": ["MediaOutlet"],
    "news": ["MediaOutlet"],
    "ngo": ["NGO"],
    "company": ["Company"],
    "companies": ["Company"],
    "tech": ["Company"],
    "official": ["Official"],
}


# ---- Simple stemming ----

def simple_stem(word: str) -> str:
    """Very simple suffix-stripping stemmer."""
    if len(word) <= 3:
        return word
    # Order matters: try longest suffixes first
    if word.endswith("ative"):
        return word[:-5]
    if word.endswith("ation"):
        return word[:-5]
    if word.endswith("ment"):
        return word[:-4]
    if word.endswith("ness"):
        return word[:-4]
    if word.endswith("ible"):
        return word[:-4]
    if word.endswith("able"):
        return word[:-4]
    if word.endswith("ious"):
        return word[:-4]
    if word.endswith("eous"):
        return word[:-4]
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("ive"):
        return word[:-3]
    if word.endswith("ting"):
        return word[:-4]
    if word.endswith("ing"):
        return word[:-3]
    if word.endswith("ted"):
        return word[:-3]
    if word.endswith("ors"):
        return word[:-3]
    if word.endswith("ers"):
        return word[:-3]
    if word.endswith("ed"):
        return word[:-2]
    if word.endswith("es"):
        return word[:-2]
    if word.endswith("er"):
        return word[:-2]
    if word.endswith("or"):
        return word[:-2]
    if word.endswith("ly"):
        return word[:-2]
    if word.endswith("al"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


# ---- Search scoring function ----

# Stopwords to skip during keyword matching
STOPWORDS = frozenset({
    "the", "and", "or", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "a", "an", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "into", "about", "that", "this",
    "it", "its", "they", "them", "their", "we", "our",
    "what", "which", "who", "whom", "how", "when", "where",
    "why", "all", "each", "every", "both", "few", "more",
    "some", "any", "no", "not", "only", "very", "just",
    "also", "than", "too", "so", "if", "but", "because",
    "across", "between", "through", "during", "before", "after",
})


def match_score(
    text: str,
    query: str,
    keywords: List[str],
    *,
    expanded_keywords: List[str] | None = None,
    bigrams: List[str] | None = None,
    idf_weights: Dict[str, float] | None = None,
) -> int:
    """Calculate relevance score between text and a search query.

    Args:
        text: The text to score (edge fact or node summary).
        query: The full search query (lowercased).
        keywords: Pre-tokenized query keywords (lowercased, len > 1).
        expanded_keywords: Synonym-expanded keywords.
        bigrams: Bigram phrases from query.
        idf_weights: IDF weights for rarity-aware scoring.

    Returns:
        Integer score (higher = more relevant). 0 means no match.
    """
    if not text:
        return 0

    text_lower = text.lower()

    # Exact full-query match
    if query in text_lower:
        return 100

    score = 0

    # Direct keyword matching (higher weight for direct matches)
    matched_direct = 0
    matched_kw_set: Set[str] = set()
    for keyword in keywords:
        if keyword in text_lower:
            # Use IDF weight if available, else default weight
            weight = int(idf_weights.get(keyword, 1.0) * 6) if idf_weights else 12
            weight = max(weight, 6)  # minimum weight
            score += weight
            matched_direct += 1
            matched_kw_set.add(keyword)

    # Stem-based matching: stem both query keywords and text words
    text_words = set(re.findall(r'[a-z]+', text_lower))
    text_stems = {simple_stem(w) for w in text_words if len(w) > 2}
    if matched_direct == 0:
        for keyword in keywords:
            kw_stem = simple_stem(keyword)
            if len(kw_stem) > 2 and kw_stem in text_stems:
                score += 7
                matched_kw_set.add(keyword)

    # Synonym/expanded keyword matching - track which original keywords matched
    expanded_match_count = 0
    if expanded_keywords:
        for ekw in expanded_keywords:
            if ekw in text_lower:
                weight = int(idf_weights.get(ekw, 1.0) * 4) if idf_weights else 8
                weight = max(weight, 4)
                score += weight
                expanded_match_count += 1
                # Track which original keyword this synonym came from
                for kw in keywords:
                    if ekw in SYNONYM_MAP.get(kw, []):
                        matched_kw_set.add(kw)

    # Multi-concept bonus: reward edges matching multiple distinct query concepts
    if len(matched_kw_set) >= 2:
        score += len(matched_kw_set) * 6


    # Bigram matching
    if bigrams:
        for bigram in bigrams:
            if bigram in text_lower:
                score += 15

    return score


def match_score_with_node_context(
    edge: Dict[str, Any],
    query: str,
    keywords: List[str],
    nodes_by_uuid: Dict[str, Dict[str, Any]],
    *,
    expanded_keywords: List[str] | None = None,
    bigrams: List[str] | None = None,
    target_labels: Set[str] | None = None,
) -> int:
    """Score an edge considering both edge text and connected node context."""
    # Score the edge fact and name
    fact_score = match_score(
        edge.get("fact", ""), query, keywords,
        expanded_keywords=expanded_keywords, bigrams=bigrams,
    )
    name_score = match_score(
        edge.get("name", ""), query, keywords,
        expanded_keywords=expanded_keywords, bigrams=bigrams,
    )
    total = fact_score + name_score

    # Score based on connected nodes
    source_uuid = edge.get("source_node_uuid", "")
    target_uuid = edge.get("target_node_uuid", "")
    source_node = nodes_by_uuid.get(source_uuid, {})
    target_node = nodes_by_uuid.get(target_uuid, {})

    # Check if connected nodes match entity type hints
    if target_labels:
        source_labels = set(source_node.get("labels", []))
        target_labels_set = set(target_node.get("labels", []))
        if source_labels & target_labels:
            total += 8
        if target_labels_set & target_labels:
            total += 8

    # Boost edges where node names/summaries match query keywords
    source_name_score = match_score(
        source_node.get("name", ""), query, keywords,
        expanded_keywords=expanded_keywords, bigrams=bigrams,
    )
    target_name_score = match_score(
        target_node.get("name", ""), query, keywords,
        expanded_keywords=expanded_keywords, bigrams=bigrams,
    )

    # If both source and target are relevant, boost
    if source_name_score > 0 and target_name_score > 0:
        total += 12

    # If edge itself didn't match but nodes did, still include with lower score
    if total == 0:
        node_boost = (source_name_score + target_name_score) // 3
        total += node_boost

    return total


def tokenize_query(query: str) -> List[str]:
    """Split a query into searchable keywords."""
    query_lower = query.lower()
    # Split on whitespace first
    raw_tokens = query_lower.replace(",", " ").replace("\u3001", " ").split()
    tokens = []
    for token in raw_tokens:
        token = token.strip().rstrip("?.:;!")
        if len(token) <= 1 or token in STOPWORDS:
            continue
        # Split hyphenated tokens but also keep the original
        if "-" in token:
            parts = [p for p in token.split("-") if len(p) > 1]
            tokens.extend(parts)
            tokens.append(token)  # Keep original for bigram/exact matching
        else:
            tokens.append(token)
    return tokens


def expand_keywords(keywords: List[str]) -> List[str]:
    """Expand keywords with synonyms and related words."""
    expanded = []
    seen = set(keywords)
    for kw in keywords:
        synonyms = SYNONYM_MAP.get(kw, [])
        for syn in synonyms:
            if syn not in seen:
                expanded.append(syn)
                seen.add(syn)
    return expanded


def get_target_edge_types(keywords: List[str]) -> Set[str]:
    """Get target edge relationship types from query keywords."""
    types: Set[str] = set()
    for kw in keywords:
        if kw in EDGE_TYPE_MAP:
            types.update(EDGE_TYPE_MAP[kw])
    return types


def get_target_labels(keywords: List[str]) -> Set[str]:
    """Get target entity labels from query keywords."""
    labels: Set[str] = set()
    for kw in keywords:
        if kw in ENTITY_TYPE_MAP:
            labels.update(ENTITY_TYPE_MAP[kw])
    return labels


def extract_bigrams(keywords: List[str]) -> List[str]:
    """Extract bigram phrases from keyword list."""
    bigrams = []
    for i in range(len(keywords) - 1):
        bigrams.append(f"{keywords[i]} {keywords[i+1]}")
    return bigrams


# ---- Result ranking ----


def compute_idf_weights(
    edges: List[Dict[str, Any]],
    keywords: List[str],
    expanded_kw: List[str],
) -> Dict[str, float]:
    """Compute inverse document frequency weights for keywords.

    Rarer keywords (appearing in fewer edges) get higher weight.
    """
    import math
    n_docs = len(edges)
    all_terms = list(set(keywords + expanded_kw))
    weights: Dict[str, float] = {}
    for term in all_terms:
        doc_count = sum(
            1 for e in edges
            if term in e.get("fact", "").lower() or term in e.get("name", "").lower()
        )
        if doc_count > 0:
            weights[term] = math.log(n_docs / doc_count) + 1.0
        else:
            weights[term] = 0.0
    return weights


def rank_edges(
    edges: List[Dict[str, Any]],
    query: str,
    keywords: List[str],
    limit: int = 15,
    *,
    nodes: List[Dict[str, Any]] | None = None,
) -> List[Tuple[int, Dict[str, Any]]]:
    """Score and rank edges by relevance to the query."""
    # Build expanded keywords and entity type labels
    exp_kw = expand_keywords(keywords)
    target_labs = get_target_labels(keywords)
    target_edge_types = get_target_edge_types(keywords)
    bigrams = extract_bigrams(keywords)

    # Compute IDF weights for rarity-aware scoring
    idf_weights = compute_idf_weights(edges, keywords, exp_kw)

    # Build node lookup if nodes provided
    nodes_by_uuid: Dict[str, Dict[str, Any]] = {}
    if nodes:
        for n in nodes:
            nodes_by_uuid[n["uuid"]] = n

    scored = []
    for edge in edges:
        if nodes_by_uuid:
            score = match_score_with_node_context(
                edge, query, keywords, nodes_by_uuid,
                expanded_keywords=exp_kw, bigrams=bigrams,
                target_labels=target_labs if target_labs else None,
            )
        else:
            score = match_score(edge.get("fact", ""), query, keywords,
                                expanded_keywords=exp_kw, bigrams=bigrams,
                                idf_weights=idf_weights)
            score += match_score(edge.get("name", ""), query, keywords,
                                 expanded_keywords=exp_kw, bigrams=bigrams,
                                 idf_weights=idf_weights)

        # Boost edges whose relationship type matches query concepts
        if target_edge_types:
            edge_name = edge.get("name", "")
            if edge_name in target_edge_types:
                # Higher boost for action-type edges (OPPOSES, SUPPORTS)
                # vs structural edges (REGULATES) which match broadly
                if edge_name in ("OPPOSES", "SUPPORTS", "COLLABORATES_WITH", "COMPETES_WITH"):
                    score += 20
                else:
                    score += 12

        # For queries about people/roles, also include WORKS_FOR edges
        # that contain relevant role titles (connects people to orgs)
        edge_name = edge.get("name", "")
        fact_lower = edge.get("fact", "").lower()
        role_terms = {"ceo", "president", "chief", "director", "chairman",
                      "founder"}
        has_exec_keyword = any(k in ("executive", "executives", "leader", "leaders")
                               for k in keywords)
        if has_exec_keyword and edge_name == "WORKS_FOR":
            for role in role_terms:
                if role in fact_lower:
                    score += 25
                    break

        if score > 0:
            scored.append((score, edge))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


def rank_nodes(
    nodes: List[Dict[str, Any]],
    query: str,
    keywords: List[str],
    limit: int = 15,
) -> List[Tuple[int, Dict[str, Any]]]:
    """Score and rank nodes by relevance to the query."""
    exp_kw = expand_keywords(keywords)
    target_labs = get_target_labels(keywords)
    bigrams = extract_bigrams(keywords)

    scored = []
    for node in nodes:
        score = match_score(node.get("name", ""), query, keywords,
                           expanded_keywords=exp_kw, bigrams=bigrams)
        score += match_score(node.get("summary", ""), query, keywords,
                            expanded_keywords=exp_kw, bigrams=bigrams)

        # Boost nodes that match target entity labels
        if target_labs:
            node_labels = set(node.get("labels", []))
            if node_labels & target_labs:
                score += 10

        if score > 0:
            scored.append((score, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


def deduplicate_facts(facts: List[str]) -> List[str]:
    """Remove duplicate facts while preserving order."""
    seen: Set[str] = set()
    result = []
    for fact in facts:
        if fact not in seen:
            seen.add(fact)
            result.append(fact)
    return result
