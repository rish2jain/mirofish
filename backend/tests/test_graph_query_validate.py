"""Read-only Cypher validation for Kuzu query API."""

import pytest

from app.services.graph_storage import StorageError, validate_read_only_kuzu_query


def test_validate_rejects_drop():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("DROP TABLE Node")


def test_validate_rejects_semicolon():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("MATCH (n:Node) RETURN n.id; MATCH (m:Node) RETURN m.id")


def test_validate_accepts_match():
    validate_read_only_kuzu_query("MATCH (n:Node) RETURN n.id LIMIT 5")


def test_validate_call_limited():
    validate_read_only_kuzu_query("CALL SHOW_TABLES() RETURN *")


def test_validate_rejects_unsafe_call():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("CALL bad_proc() RETURN *")


def test_validate_rejects_call_proc_that_contains_allowed_substring():
    """Substring allowlist would wrongly accept SHOW_TABLES inside SHOW_TABLES_AND_DROP."""
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("CALL SHOW_TABLES_AND_DROP() RETURN *")


def test_validate_rejects_create():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("CREATE (n:Node) RETURN n")


def test_validate_rejects_create_after_match():
    """CREATE must be rejected when the query starts with MATCH (not only CREATE NODE/REL)."""
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("MATCH (n:Node) CREATE (m:Other) RETURN n")


def test_validate_rejects_create_table():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("CREATE TABLE t (id INT64)")


def test_validate_rejects_delete():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("MATCH (n:Node) DELETE n")


def test_validate_rejects_merge():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("MATCH (n:Node) MERGE (m:Other {id:1})")


def test_validate_rejects_remove():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("MATCH (n:Node) REMOVE n.property")


def test_validate_rejects_set():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("MATCH (n:Node) SET n.name = 'x'")


def test_validate_rejects_detach_delete():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("MATCH (n:Node) DETACH DELETE n")


def test_validate_case_insensitive_drop():
    with pytest.raises(StorageError):
        validate_read_only_kuzu_query("drop table Node")


def test_execute_read_only_query_fetches_at_most_max_rows(tmp_path):
    """KuzuDBStorage uses QueryResult.get_n (not get_all) to bound row materialization."""
    from app.services.graph_storage import KuzuDBStorage

    storage = KuzuDBStorage(str(tmp_path / "kuzu_graph"))
    ts = "2020-01-01T00:00:00Z"
    for i in range(20):
        storage.add_node(
            {
                "id": f"n{i:03d}",
                "name": f"Person-{i}",
                "label": "Person",
                "summary": "",
                "facts": [],
                "attributes": {},
                "created_at": ts,
                "updated_at": ts,
            }
        )
    out = storage.execute_read_only_query("MATCH (n:Node) RETURN n.id", max_rows=7)
    assert out["columns"]
    assert len(out["rows"]) == 7
    assert out["truncated"] is True

    limited = storage.execute_read_only_query("MATCH (n:Node) RETURN n.id LIMIT 4", max_rows=100)
    assert len(limited["rows"]) == 4
    assert limited["truncated"] is False
