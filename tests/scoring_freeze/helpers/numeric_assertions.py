from typing import Any, Mapping


def assert_hard_frozen_number(
    payload: Mapping[str, Any],
    field_path: str,
    expected_value: float | int | None,
) -> None:
    actual_value = _get_by_path(payload, field_path)
    assert actual_value == expected_value, (
        f"Hard-frozen numeric mismatch for {field_path}: "
        f"expected={expected_value!r} actual={actual_value!r}"
    )


def assert_outward_projected_number(
    payload: Mapping[str, Any],
    field_path: str,
    expected_value: float | int | None,
) -> None:
    actual_value = _get_by_path(payload, field_path)
    assert actual_value == expected_value, (
        f"Outward projected numeric mismatch for {field_path}: "
        f"expected={expected_value!r} actual={actual_value!r}"
    )


def assert_soft_presentation_number(
    payload: Mapping[str, Any],
    field_path: str,
    expected_value: float | int | None,
) -> None:
    actual_value = _get_by_path(payload, field_path)
    if expected_value is None:
        return
    assert actual_value is not None, f"Missing soft numeric field {field_path}"
    assert isinstance(actual_value, (int, float)), (
        f"Soft numeric field {field_path} must be numeric"
    )


def _get_by_path(payload: Mapping[str, Any], field_path: str) -> Any:
    current: Any = payload
    for token in field_path.split("."):
        if not isinstance(current, Mapping) or token not in current:
            return None
        current = current[token]
    return current
