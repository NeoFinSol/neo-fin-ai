"""
Property-based tests for src/utils/masking.py
Feature: analysis-history-visualization
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings
from hypothesis import strategies as st

from src.utils.masking import mask_analysis_data


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_numeric = st.one_of(
    st.integers(min_value=-10_000_000, max_value=10_000_000),
    st.floats(
        min_value=-10_000_000.0,
        max_value=10_000_000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
)

_metrics_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=_numeric,
    min_size=0,
    max_size=10,
)

_ratios_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20),
    values=_numeric,
    min_size=0,
    max_size=10,
)

_score_strategy = st.fixed_dictionaries(
    {
        "score": st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        "risk_level": st.sampled_from(["low", "medium", "high"]),
        "factors": st.lists(st.text(max_size=50), max_size=5),
        "normalized_scores": st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            max_size=5,
        ),
    }
)

_nlp_strategy = st.fixed_dictionaries(
    {
        "risks": st.lists(st.text(max_size=50), max_size=3),
        "key_factors": st.lists(st.text(max_size=50), max_size=3),
        "recommendations": st.lists(st.text(max_size=50), max_size=3),
    }
)


def analysis_data_strategy():
    """
    Generates dicts that mimic the structure of analysis data passed to
    mask_analysis_data().  The top-level dict has a 'data' key whose value
    mirrors the JSONB 'result.data' structure from src/tasks.py.
    """
    inner = st.fixed_dictionaries(
        {
            "metrics": _metrics_strategy,
            "ratios": _ratios_strategy,
            "text": st.text(max_size=200),
            "score": _score_strategy,
            "nlp": _nlp_strategy,
        }
    )
    return st.fixed_dictionaries(
        {
            "status": st.sampled_from(["completed", "processing", "failed"]),
            "filename": st.text(min_size=1, max_size=50),
            "data": inner,
        }
    )


# ---------------------------------------------------------------------------
# Property 5: Маскировка числовых значений
# ---------------------------------------------------------------------------


@given(analysis_data_strategy())
@settings(max_examples=100)
def test_mask_replaces_numbers_preserves_score(data):
    # Feature: analysis-history-visualization, Property 5: маскировка числовых значений
    # Validates: Requirements 4.1, 4.4
    result = mask_analysis_data(data, True)

    inner_orig = data["data"]
    inner_result = result["data"]

    # All numeric values in metrics and ratios must be replaced with non-numeric (strings)
    for key, value in inner_orig["metrics"].items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            assert not isinstance(inner_result["metrics"][key], (int, float)), (
                f"metrics[{key!r}] should be masked but got {inner_result['metrics'][key]!r}"
            )

    for key, value in inner_orig["ratios"].items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            assert not isinstance(inner_result["ratios"][key], (int, float)), (
                f"ratios[{key!r}] should be masked but got {inner_result['ratios'][key]!r}"
            )

    # score, risk_level, factors, normalized_scores, nlp must be identical to originals
    assert inner_result["score"] == inner_orig["score"], "score must be preserved"
    assert inner_result["nlp"] == inner_orig["nlp"], "nlp must be preserved"


# ---------------------------------------------------------------------------
# Property 6: Identity при demo_mode=False
# ---------------------------------------------------------------------------


@given(analysis_data_strategy())
@settings(max_examples=100)
def test_mask_identity_when_demo_false(data):
    # Feature: analysis-history-visualization, Property 6: identity при demo_mode=False
    # Validates: Requirements 4.5
    result = mask_analysis_data(data, False)
    assert result == data


# ---------------------------------------------------------------------------
# Property 7: Идемпотентность маскировки
# ---------------------------------------------------------------------------


@given(analysis_data_strategy())
@settings(max_examples=100)
def test_mask_idempotent(data):
    # Feature: analysis-history-visualization, Property 7: идемпотентность маскировки
    # Validates: Requirements 4.8
    once = mask_analysis_data(data, True)
    twice = mask_analysis_data(once, True)
    assert twice == once, (
        "Double masking must equal single masking (idempotency)"
    )


# ---------------------------------------------------------------------------
# Unit-тесты для граничных случаев
# Validates: Requirements 4.5, 4.7
# ---------------------------------------------------------------------------


def test_empty_dict_demo_false():
    assert mask_analysis_data({}, False) == {}


def test_empty_dict_demo_true():
    assert mask_analysis_data({}, True) == {}


def test_empty_data_key_no_error():
    result = mask_analysis_data({"data": {}}, True)
    assert result == {"data": {}}


def test_empty_metrics_and_ratios_no_error():
    data = {"data": {"metrics": {}, "ratios": {}}}
    result = mask_analysis_data(data, True)
    assert result["data"]["metrics"] == {}
    assert result["data"]["ratios"] == {}


def test_text_replaced_in_demo_mode():
    data = {"data": {"text": "secret"}}
    result = mask_analysis_data(data, True)
    assert result["data"]["text"] == "[DEMO: текст скрыт]"


def test_bool_values_not_masked():
    data = {"data": {"metrics": {"flag": True}, "ratios": {"active": False}}}
    result = mask_analysis_data(data, True)
    assert result["data"]["metrics"]["flag"] is True
    assert result["data"]["ratios"]["active"] is False


def test_none_values_not_masked():
    data = {"data": {"metrics": {"value": None}, "ratios": {"ratio": None}}}
    result = mask_analysis_data(data, True)
    assert result["data"]["metrics"]["value"] is None
    assert result["data"]["ratios"]["ratio"] is None


def test_negative_number_sign_preserved():
    data = {"data": {"metrics": {"loss": -42.1}}}
    result = mask_analysis_data(data, True)
    assert result["data"]["metrics"]["loss"] == "-XX.X"


def test_zero_masked_as_x():
    data = {"data": {"metrics": {"val": 0}, "ratios": {"r": 0.0}}}
    result = mask_analysis_data(data, True)
    assert result["data"]["metrics"]["val"] == "X"
    assert result["data"]["ratios"]["r"] == "X"
