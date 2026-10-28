import pytest
from fastapi import HTTPException
from app.rag.pipeline import NO_EVIDENCE, _validated_answer, apply_relevance_gate


def test_invalid_citation_indexes_are_removed():
    assert _validated_answer("结论见 [1] 和 [8]。", 2) == "结论见 [1] 和 。"


def test_no_evidence_response_is_explicitly_unreferenced():
    assert "没有检索到" in NO_EVIDENCE


def test_reranker_gate_abstains_below_threshold():
    assert apply_relevance_gate([{"score": 0.19}], "dense+rerank", 0.2) == []
    assert apply_relevance_gate([{"score": 0.2}], "dense+rerank", 0.2) == [{"score": 0.2}]


def test_reranker_gate_fails_closed_if_model_unavailable():
    with pytest.raises(HTTPException) as error:
        apply_relevance_gate([{"score": 0.9}], "dense (reranker unavailable)", 0.2)
    assert error.value.status_code == 503


def test_reranker_gate_abstains_without_candidates_even_if_reranker_is_skipped():
    assert apply_relevance_gate([], "dense", 0.2) == []
