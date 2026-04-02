#!/usr/bin/env python3
"""Contest demo smoke checks for NeoFin AI."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests


class DemoSmokeError(RuntimeError):
    """Raised when a smoke scenario fails."""


def _load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalize_api_prefix(prefix: str) -> str:
    trimmed = prefix.strip()
    if not trimmed or trimmed == "/":
        return ""
    return "/" + trimmed.strip("/")


def _build_url(base_url: str, api_prefix: str, endpoint: str) -> str:
    normalized_prefix = _normalize_api_prefix(api_prefix)
    return f"{base_url.rstrip('/')}{normalized_prefix}{endpoint}"


def _require_payload_dict(payload: Any, message: str) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    raise DemoSmokeError(message)


def _poll_single_result(
    session: requests.Session,
    result_url: str,
    max_wait_seconds: int,
    poll_seconds: float,
) -> dict[str, Any]:
    started_at = time.monotonic()
    while True:
        response = session.get(result_url, timeout=120)
        response.raise_for_status()
        payload = _require_payload_dict(
            response.json(),
            f"Unexpected /result payload type at {result_url}",
        )
        status = payload.get("status")
        if status == "completed":
            return payload
        if status in {"failed", "cancelled"}:
            raise DemoSmokeError(f"Single analysis ended with status={status}")
        if time.monotonic() - started_at > max_wait_seconds:
            raise DemoSmokeError(
                f"Timeout waiting for single analysis ({max_wait_seconds}s)"
            )
        time.sleep(poll_seconds)


def _poll_multi_result(
    session: requests.Session,
    result_url: str,
    max_wait_seconds: int,
    poll_seconds: float,
) -> dict[str, Any]:
    started_at = time.monotonic()
    while True:
        response = session.get(result_url, timeout=120)
        if response.status_code == 422:
            raise DemoSmokeError("Multi-period analysis failed with status=422")
        response.raise_for_status()
        payload = _require_payload_dict(
            response.json(),
            f"Unexpected /multi-analysis payload type at {result_url}",
        )
        status = payload.get("status")
        if status == "completed":
            return payload
        if status in {"failed", "cancelled"}:
            raise DemoSmokeError(f"Multi analysis ended with status={status}")
        if time.monotonic() - started_at > max_wait_seconds:
            raise DemoSmokeError(
                f"Timeout waiting for multi analysis ({max_wait_seconds}s)"
            )
        time.sleep(poll_seconds)


def _assert_metric_with_tolerance(
    scenario_id: str,
    metric_key: str,
    expected: float,
    actual: Any,
    abs_tolerance: float,
) -> None:
    if actual is None:
        raise DemoSmokeError(
            f"{scenario_id}: metric '{metric_key}' is None, expected {expected}"
        )
    if not isinstance(actual, (int, float)):
        raise DemoSmokeError(
            f"{scenario_id}: metric '{metric_key}' has invalid type {type(actual).__name__}"
        )
    delta = abs(float(actual) - expected)
    if delta > abs_tolerance:
        raise DemoSmokeError(
            f"{scenario_id}: metric '{metric_key}' mismatch (expected={expected}, actual={actual}, "
            f"abs_tolerance={abs_tolerance})"
        )


def _assert_task_visible_in_history(
    session: requests.Session,
    list_url: str,
    task_id: str,
) -> None:
    response = session.get(list_url, timeout=120)
    response.raise_for_status()
    payload = _require_payload_dict(
        response.json(),
        f"Unexpected /analyses payload type at {list_url}",
    )
    items = payload.get("items")
    if not isinstance(items, list):
        raise DemoSmokeError("History payload has invalid 'items' field")
    found = any(
        isinstance(item, dict) and item.get("task_id") == task_id for item in items
    )
    if not found:
        raise DemoSmokeError(f"Task {task_id} not found in /analyses history")


def _run_single_scenario(
    session: requests.Session,
    scenario: dict[str, Any],
    case_map: dict[str, dict[str, Any]],
    fixture_root: Path,
    base_url: str,
    api_prefix: str,
    max_wait_seconds: int,
    poll_seconds: float,
    skip_history: bool,
) -> None:
    scenario_id = scenario["id"]
    case_id = scenario["case_id"]
    case = case_map.get(case_id)
    if case is None:
        raise DemoSmokeError(f"{scenario_id}: unknown case_id '{case_id}' in manifest")

    file_path = fixture_root / case["filename"]
    if not file_path.exists():
        raise DemoSmokeError(f"{scenario_id}: fixture not found: {file_path}")

    upload_url = _build_url(base_url, api_prefix, "/upload")
    with file_path.open("rb") as file:
        response = session.post(
            upload_url,
            files={"file": (file_path.name, file, "application/pdf")},
            timeout=120,
        )
    response.raise_for_status()
    upload_payload = _require_payload_dict(
        response.json(),
        f"{scenario_id}: unexpected /upload payload type",
    )
    task_id = upload_payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise DemoSmokeError(f"{scenario_id}: invalid task_id in upload response")

    result_url = _build_url(base_url, api_prefix, f"/result/{task_id}")
    result_payload = _poll_single_result(
        session=session,
        result_url=result_url,
        max_wait_seconds=max_wait_seconds,
        poll_seconds=poll_seconds,
    )

    data_block = result_payload.get("data")
    if not isinstance(data_block, dict):
        data_block = result_payload
    metrics_block = data_block.get("metrics")
    if not isinstance(metrics_block, dict):
        raise DemoSmokeError(f"{scenario_id}: result payload has no metrics block")

    headline_metrics = scenario.get("headline_metrics", {})
    for metric_key, expected_payload in headline_metrics.items():
        expected_info = _require_payload_dict(
            expected_payload,
            f"{scenario_id}: invalid headline metric config for {metric_key}",
        )
        expected_value = expected_info.get("expected")
        if not isinstance(expected_value, (int, float)):
            raise DemoSmokeError(
                f"{scenario_id}: expected value missing for {metric_key}"
            )
        abs_tolerance = float(expected_info.get("abs_tolerance", 0.0))
        _assert_metric_with_tolerance(
            scenario_id=scenario_id,
            metric_key=metric_key,
            expected=float(expected_value),
            actual=metrics_block.get(metric_key),
            abs_tolerance=abs_tolerance,
        )

    if not skip_history:
        analyses_url = _build_url(
            base_url, api_prefix, "/analyses?page=1&page_size=100"
        )
        _assert_task_visible_in_history(
            session=session, list_url=analyses_url, task_id=task_id
        )

    print(f"[OK] {scenario_id}: completed task_id={task_id}")


def _run_multi_scenario(
    session: requests.Session,
    scenario: dict[str, Any],
    case_map: dict[str, dict[str, Any]],
    fixture_root: Path,
    base_url: str,
    api_prefix: str,
    max_wait_seconds: int,
    poll_seconds: float,
) -> None:
    scenario_id = scenario["id"]
    items = scenario.get("items", [])
    if not isinstance(items, list) or not items:
        raise DemoSmokeError(f"{scenario_id}: invalid multi-period items")

    payload_files: list[tuple[str, tuple[str, Any, str]]] = []
    payload_periods: list[tuple[str, str]] = []

    with contextlib.ExitStack() as exit_stack:
        for item in items:
            item_payload = _require_payload_dict(
                item, f"{scenario_id}: invalid item config"
            )
            case_id = item_payload.get("case_id")
            period_label = item_payload.get("period_label")
            if not isinstance(case_id, str) or not isinstance(period_label, str):
                raise DemoSmokeError(
                    f"{scenario_id}: item must contain string case_id and period_label"
                )
            case = case_map.get(case_id)
            if case is None:
                raise DemoSmokeError(f"{scenario_id}: unknown case_id '{case_id}'")
            file_path = fixture_root / case["filename"]
            if not file_path.exists():
                raise DemoSmokeError(f"{scenario_id}: fixture not found: {file_path}")

            file_handle = exit_stack.enter_context(file_path.open("rb"))
            payload_files.append(
                ("files", (file_path.name, file_handle, "application/pdf"))
            )
            payload_periods.append(("periods", period_label))

        start_url = _build_url(base_url, api_prefix, "/multi-analysis")
        response = session.post(
            start_url,
            files=payload_files,
            data=payload_periods,
            timeout=120,
        )
        response.raise_for_status()
        start_payload = _require_payload_dict(
            response.json(),
            f"{scenario_id}: unexpected /multi-analysis start payload type",
        )
        session_id = start_payload.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise DemoSmokeError(f"{scenario_id}: invalid session_id in start response")

    result_url = _build_url(base_url, api_prefix, f"/multi-analysis/{session_id}")
    result_payload = _poll_multi_result(
        session=session,
        result_url=result_url,
        max_wait_seconds=max_wait_seconds,
        poll_seconds=poll_seconds,
    )

    periods = result_payload.get("periods")
    if not isinstance(periods, list):
        raise DemoSmokeError(f"{scenario_id}: completed payload has invalid periods")

    expect = _require_payload_dict(
        scenario.get("expect", {}),
        f"{scenario_id}: invalid expect block",
    )
    expected_period_count = expect.get("period_count")
    if isinstance(expected_period_count, int) and len(periods) != expected_period_count:
        raise DemoSmokeError(
            f"{scenario_id}: expected period_count={expected_period_count}, got={len(periods)}"
        )

    expected_labels = expect.get("period_labels")
    if isinstance(expected_labels, list):
        actual_labels = [
            period.get("period_label") for period in periods if isinstance(period, dict)
        ]
        if actual_labels != expected_labels:
            raise DemoSmokeError(
                f"{scenario_id}: period labels mismatch (expected={expected_labels}, got={actual_labels})"
            )

    print(f"[OK] {scenario_id}: completed session_id={session_id}")


def _run_scenarios(
    session: requests.Session,
    manifest: dict[str, Any],
    fixture_root: Path,
    base_url: str,
    api_prefix: str,
    max_wait_seconds: int,
    poll_seconds: float,
    selected_scenarios: set[str] | None,
    skip_history: bool,
) -> None:
    cases = manifest.get("local_regression_cases", [])
    scenarios = manifest.get("demo_scenarios", [])
    if not isinstance(cases, list) or not isinstance(scenarios, list):
        raise DemoSmokeError(
            "Manifest must contain list fields: local_regression_cases, demo_scenarios"
        )

    case_map: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_payload = _require_payload_dict(case, "Manifest case entry must be object")
        case_id = case_payload.get("id")
        if not isinstance(case_id, str):
            raise DemoSmokeError(
                "Each case in local_regression_cases must have string id"
            )
        case_map[case_id] = case_payload

    for scenario in scenarios:
        scenario_payload = _require_payload_dict(
            scenario, "Manifest scenario entry must be object"
        )
        scenario_id = scenario_payload.get("id")
        kind = scenario_payload.get("kind")
        if not isinstance(scenario_id, str) or not isinstance(kind, str):
            raise DemoSmokeError("Each demo_scenario must include string id and kind")
        if selected_scenarios is not None and scenario_id not in selected_scenarios:
            continue

        print(f"[RUN] {scenario_id} ({kind})")
        if kind == "single":
            _run_single_scenario(
                session=session,
                scenario=scenario_payload,
                case_map=case_map,
                fixture_root=fixture_root,
                base_url=base_url,
                api_prefix=api_prefix,
                max_wait_seconds=max_wait_seconds,
                poll_seconds=poll_seconds,
                skip_history=skip_history,
            )
            continue
        if kind == "multi_period":
            _run_multi_scenario(
                session=session,
                scenario=scenario_payload,
                case_map=case_map,
                fixture_root=fixture_root,
                base_url=base_url,
                api_prefix=api_prefix,
                max_wait_seconds=max_wait_seconds,
                poll_seconds=poll_seconds,
            )
            continue
        raise DemoSmokeError(f"Unsupported scenario kind: {kind}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run contest demo smoke scenarios.")
    parser.add_argument(
        "--base-url",
        default="http://localhost",
        help="Base URL for API requests (for example: http://localhost or https://demo.example.com).",
    )
    parser.add_argument(
        "--api-prefix",
        default="/api",
        help="API prefix for routed endpoints (default: /api). Use '/' for direct backend routes.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("API_KEY", ""),
        help="X-API-Key value. Defaults to environment variable API_KEY.",
    )
    parser.add_argument(
        "--manifest",
        default="tests/data/demo_manifest.json",
        help="Path to demo manifest JSON file.",
    )
    parser.add_argument(
        "--fixtures-root",
        default="",
        help="Override fixtures root. By default uses manifest.fixtures_root.",
    )
    parser.add_argument(
        "--max-wait-seconds",
        type=int,
        default=600,
        help="Maximum wait time for each scenario completion.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=2.5,
        help="Polling interval in seconds.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario ID from manifest. Can be passed multiple times. Default runs all.",
    )
    parser.add_argument(
        "--skip-history-check",
        action="store_true",
        help="Skip verification that task appears in /analyses.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.api_key:
        print(
            "API key is required. Pass --api-key or set API_KEY environment variable."
        )
        return 2

    manifest_path = Path(args.manifest).resolve()
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 2

    manifest = _load_manifest(manifest_path)
    if args.fixtures_root:
        fixture_root = Path(args.fixtures_root).resolve()
    else:
        manifest_fixture_root = Path(manifest.get("fixtures_root", "tests/PDFforTests"))
        if manifest_fixture_root.is_absolute():
            fixture_root = manifest_fixture_root
        else:
            repo_root = manifest_path.parents[2]
            fixture_root = (repo_root / manifest_fixture_root).resolve()
    if not fixture_root.exists():
        print(f"Fixtures root not found: {fixture_root}")
        return 2

    selected_scenarios = set(args.scenario) if args.scenario else None
    session = requests.Session()
    session.headers.update({"X-API-Key": args.api_key})

    try:
        _run_scenarios(
            session=session,
            manifest=manifest,
            fixture_root=fixture_root,
            base_url=args.base_url,
            api_prefix=args.api_prefix,
            max_wait_seconds=args.max_wait_seconds,
            poll_seconds=args.poll_seconds,
            selected_scenarios=selected_scenarios,
            skip_history=args.skip_history_check,
        )
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(f"HTTP error during demo smoke: status={status}, detail={exc}")
        return 1
    except DemoSmokeError as exc:
        print(f"Demo smoke failed: {exc}")
        return 1
    finally:
        session.close()

    print("Demo smoke completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
