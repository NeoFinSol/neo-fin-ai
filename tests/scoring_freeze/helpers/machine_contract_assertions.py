from typing import Any, Mapping


def assert_machine_status_contract(
    payload: Mapping[str, Any],
    expected_status_fields: Mapping[str, Any],
) -> None:
    for field_path, expected_value in expected_status_fields.items():
        actual_value = _get_by_path(payload, field_path)
        assert actual_value == expected_value, (
            f"Status mismatch for {field_path}: "
            f"expected={expected_value!r} actual={actual_value!r}"
        )


def assert_machine_reason_contract(
    payload: Mapping[str, Any],
    expected_reason_fields: Mapping[str, Any],
) -> None:
    for field_path, expected_value in expected_reason_fields.items():
        actual_value = _get_by_path(payload, field_path)
        assert actual_value == expected_value, (
            f"Reason mismatch for {field_path}: "
            f"expected={expected_value!r} actual={actual_value!r}"
        )


def assert_machine_methodology_contract(
    payload: Mapping[str, Any],
    expected_methodology_fields: Mapping[str, Any],
) -> None:
    for field_path, expected_value in expected_methodology_fields.items():
        actual_value = _get_by_path(payload, field_path)
        assert actual_value == expected_value, (
            f"Methodology mismatch for {field_path}: "
            f"expected={expected_value!r} actual={actual_value!r}"
        )


def _get_by_path(payload: Mapping[str, Any], field_path: str) -> Any:
    current: Any = payload
    for token in field_path.split("."):
        if not isinstance(current, Mapping) or token not in current:
            return None
        current = current[token]
    return current
