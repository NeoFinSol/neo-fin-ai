from typing import Any, Mapping


def assert_annualization_behavior(
    payload: Mapping[str, Any],
    expected_annualization_fields: Mapping[str, Any],
) -> None:
    for field_path, expected_value in expected_annualization_fields.items():
        actual_value = _get_by_path(payload, field_path)
        assert actual_value == expected_value, (
            f"Annualization mismatch for {field_path}: "
            f"expected={expected_value!r} actual={actual_value!r}"
        )


def assert_guardrail_behavior(
    payload: Mapping[str, Any],
    expected_guardrail_fields: Mapping[str, Any],
) -> None:
    for field_path, expected_value in expected_guardrail_fields.items():
        actual_value = _get_by_path(payload, field_path)
        assert actual_value == expected_value, (
            f"Guardrail mismatch for {field_path}: "
            f"expected={expected_value!r} actual={actual_value!r}"
        )


def _get_by_path(payload: Mapping[str, Any], field_path: str) -> Any:
    current: Any = payload
    for token in field_path.split("."):
        if not isinstance(current, Mapping) or token not in current:
            return None
        current = current[token]
    return current
