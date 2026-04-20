from typing import Any, Mapping

from tests.scoring_freeze.fixtures.models import PayloadFieldRule


def assert_payload_matches_matrix(
    payload: Mapping[str, Any],
    payload_rules: tuple[PayloadFieldRule, ...],
) -> None:
    assert_required_fields_present(payload, payload_rules)
    assert_optional_field_omission_rules(payload, payload_rules)
    assert_field_types(payload, payload_rules)


def assert_required_fields_present(
    payload: Mapping[str, Any],
    payload_rules: tuple[PayloadFieldRule, ...],
) -> None:
    for rule in payload_rules:
        value = _get_by_path(payload, rule.field_path)
        if rule.required:
            assert value is not _MISSING, f"Missing required field: {rule.field_path}"


def assert_optional_field_omission_rules(
    payload: Mapping[str, Any],
    payload_rules: tuple[PayloadFieldRule, ...],
) -> None:
    for rule in payload_rules:
        value = _get_by_path(payload, rule.field_path)
        if rule.omission_rule == "not_applicable":
            continue
        if rule.omission_rule == "absent":
            assert value is _MISSING, f"Field must be absent: {rule.field_path}"
        elif rule.omission_rule == "null":
            assert value is None, f"Field must be null: {rule.field_path}"
        elif rule.omission_rule == "empty_container":
            assert value in (
                [],
                {},
            ), f"Field must be empty container: {rule.field_path}"


def assert_field_types(
    payload: Mapping[str, Any],
    payload_rules: tuple[PayloadFieldRule, ...],
) -> None:
    for rule in payload_rules:
        value = _get_by_path(payload, rule.field_path)
        if value is _MISSING:
            continue
        if value is None:
            assert rule.nullable, f"Non-nullable field is null: {rule.field_path}"
            continue
        _assert_expected_type(rule.field_type, value, rule.field_path)


def _assert_expected_type(field_type: str, value: Any, field_path: str) -> None:
    if field_type == "float":
        assert isinstance(value, (int, float)), f"{field_path} must be numeric"
    elif field_type == "str":
        assert isinstance(value, str), f"{field_path} must be string"
    elif field_type == "list":
        assert isinstance(value, list), f"{field_path} must be list"
    elif field_type == "dict":
        assert isinstance(value, dict), f"{field_path} must be dict"
    else:
        raise AssertionError(f"Unknown field type {field_type} for {field_path}")


def _get_by_path(payload: Mapping[str, Any], field_path: str) -> Any:
    current: Any = payload
    for token in field_path.split("."):
        if not isinstance(current, Mapping) or token not in current:
            return _MISSING
        current = current[token]
    return current


_MISSING = object()
