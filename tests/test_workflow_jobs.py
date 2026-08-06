from __future__ import annotations

import pytest

from app.workflow_jobs import PortraitWorkflowStore


def test_workflow_store_persists_between_instances(tmp_path) -> None:
    database = tmp_path / "workflow.db"
    first = PortraitWorkflowStore(database)
    created = first.create(
        filename="portrait.jpg",
        style_id="soft_watercolor",
        prompt_id="prompt-123",
        payload={"source": "upload"},
    )

    second = PortraitWorkflowStore(database)
    loaded = second.get(created.id)

    assert loaded.id == created.id
    assert loaded.prompt_id == "prompt-123"
    assert loaded.payload == {"source": "upload"}


def test_workflow_store_updates_status_and_payload(tmp_path) -> None:
    store = PortraitWorkflowStore(tmp_path / "workflow.db")
    created = store.create(
        filename=None,
        style_id="premium_chibi",
        prompt_id=None,
        payload={},
        status="queued",
        stage="accepted",
        progress=5,
    )

    updated = store.update(
        created.id,
        status="generating",
        stage="model_inference",
        progress=50,
        payload_patch={"attempt": 1},
    )

    assert updated.status == "generating"
    assert updated.stage == "model_inference"
    assert updated.progress == 50
    assert updated.payload["attempt"] == 1


def test_terminal_workflow_cannot_restart(tmp_path) -> None:
    store = PortraitWorkflowStore(tmp_path / "workflow.db")
    created = store.create(
        filename=None,
        style_id="premium_chibi",
        prompt_id=None,
        payload={},
        status="failed",
        stage="generation_failed",
        progress=100,
    )

    with pytest.raises(ValueError, match="terminal"):
        store.update(created.id, status="generating")


def test_workflow_progress_is_validated(tmp_path) -> None:
    store = PortraitWorkflowStore(tmp_path / "workflow.db")

    with pytest.raises(ValueError, match="between 0 and 100"):
        store.create(
            filename=None,
            style_id="premium_chibi",
            prompt_id=None,
            payload={},
            progress=101,
        )
