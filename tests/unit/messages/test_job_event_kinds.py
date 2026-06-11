"""§8.2 — event-kind body shape validators."""

from __future__ import annotations

import pytest

from arcp._messages.event_bodies import (
    ArtifactRefBody,
    MetricBody,
    ToolCallBody,
    ToolResultBody,
)
from arcp._messages.execution import (
    EVENT_KINDS,
    JobEventPayload,
    validate_metric_body,
    validate_progress_body,
    validate_result_chunk_body,
)


@pytest.mark.parametrize("kind", EVENT_KINDS)
def test_each_kind_accepted(kind: str) -> None:
    p = JobEventPayload(kind=kind, ts="2026-05-14T12:00:00Z", body={})
    assert p.kind == kind


def test_unknown_kind_rejected() -> None:
    with pytest.raises(Exception):
        JobEventPayload(kind="unknown", ts="2026-05-14T12:00:00Z", body={})


def test_vendor_kind_accepted() -> None:
    p = JobEventPayload(kind="x-vendor.thing", ts="2026-05-14T12:00:00Z", body={})
    assert p.kind == "x-vendor.thing"


def test_progress_validators() -> None:
    validate_progress_body({"current": 5, "total": 10})
    with pytest.raises(ValueError):
        validate_progress_body({"current": -1})
    with pytest.raises(ValueError):
        validate_progress_body({"current": 11, "total": 10})


def test_result_chunk_validators() -> None:
    validate_result_chunk_body(
        {"result_id": "r1", "chunk_seq": 0, "data": "x", "encoding": "utf8", "more": True}
    )
    with pytest.raises(ValueError):
        validate_result_chunk_body({"result_id": "r1", "chunk_seq": 0})
    with pytest.raises(ValueError):
        validate_result_chunk_body(
            {"result_id": "r1", "chunk_seq": 0, "data": "x", "encoding": "binary", "more": True}
        )


def test_metric_validators() -> None:
    validate_metric_body({"name": "cost.fetch", "value": 1.0, "unit": "USD"})
    validate_metric_body({"name": "n", "value": -1})  # non-cost negative ok
    with pytest.raises(ValueError):
        validate_metric_body({"name": "cost.fetch", "value": -0.5})
    with pytest.raises(ValueError):
        validate_metric_body({"name": "", "value": 1})


def test_event_body_field_names_match_spec_8_2() -> None:
    """#67: TypedDict body fields use the §8.2 names verbatim."""
    assert set(ToolCallBody.__annotations__) == {"tool", "args", "call_id"}
    assert set(ToolResultBody.__annotations__) == {"call_id", "result", "error"}
    assert set(MetricBody.__annotations__) == {"name", "value", "unit", "dimensions"}
    assert set(ArtifactRefBody.__annotations__) == {"uri", "content_type", "byte_size", "sha256"}


def test_spec_8_2_example_bodies_round_trip() -> None:
    """A spec §8.2-shaped body survives wire round-trip without renaming."""
    bodies = {
        "tool_call": {"tool": "search", "args": {"q": "x"}, "call_id": "c1"},
        "tool_result": {"call_id": "c1", "result": {"hits": 3}},
        "artifact_ref": {
            "uri": "s3://bucket/report.pdf",
            "content_type": "application/pdf",
            "byte_size": 1024,
            "sha256": "ab" * 32,
        },
        "metric": {"name": "tokens.in", "value": 12, "unit": "tokens", "dimensions": {"m": "x"}},
    }
    for kind, body in bodies.items():
        p = JobEventPayload(kind=kind, ts="2026-05-14T12:00:00Z", body=body)
        reparsed = JobEventPayload.model_validate(p.model_dump(mode="json"))
        assert reparsed.body == body
