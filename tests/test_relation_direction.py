"""Test V1.13 relation direction queries"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.queries.relation_query import RelationQuery
from src.core import Config


def test_relation_query_by_source_concept():
    query = RelationQuery(Config())
    results = query.search_by_relation(relation="compliance", source_concept="finance")
    assert isinstance(results, list)


def test_relation_query_by_target_concept():
    query = RelationQuery(Config())
    results = query.search_by_relation(relation="compliance", target_concept="security")
    assert isinstance(results, list)


def test_relation_query_all_filters():
    query = RelationQuery(Config())
    results = query.search_by_relation(relation="compliance", source_concept="finance", target_concept="security")
    assert isinstance(results, list)


def test_relation_query_no_results_for_unknown_relation():
    query = RelationQuery(Config())
    results = query.search_by_relation(relation="loves")
    assert results == []


def test_get_relations_empty_for_unknown_artifact():
    query = RelationQuery(Config())
    assert query.get_relations("does-not-exist-000") == {}


def test_get_incoming_empty_for_unknown_artifact():
    query = RelationQuery(Config())
    assert query.get_incoming("does-not-exist-000") == []
