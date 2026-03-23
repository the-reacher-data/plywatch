from __future__ import annotations

from plywatch.task.families import TaskFamilyClassifier, build_section_counts
from plywatch.task.models import TaskSnapshot


def test_family_classifier_groups_canvas_members_under_one_family() -> None:
    classifier = TaskFamilyClassifier()
    snapshots = [
        TaskSnapshot(
            uuid="header-1",
            kind="unknown",
            state="succeeded",
            root_id="header-1",
            canvas_kind="chord",
            canvas_id="canvas-1",
            canvas_role="header",
            first_seen_at="2026-03-19T00:00:01+00:00",
        ),
        TaskSnapshot(
            uuid="header-2",
            kind="unknown",
            state="succeeded",
            root_id="header-2",
            canvas_kind="chord",
            canvas_id="canvas-1",
            canvas_role="header",
            first_seen_at="2026-03-19T00:00:02+00:00",
        ),
        TaskSnapshot(
            uuid="body-1",
            kind="unknown",
            state="succeeded",
            root_id="header-2",
            parent_id="header-2",
            canvas_kind="chord",
            canvas_id="canvas-1",
            canvas_role="body",
            first_seen_at="2026-03-19T00:00:03+00:00",
        ),
    ]

    families = classifier.build_families(snapshots)

    assert len(families) == 1
    assert families[0].key == "canvas:canvas-1"
    assert {item.uuid for item in families[0].items} == {"header-1", "header-2", "body-1"}


def test_family_classifier_detaches_waiting_children_from_running_family() -> None:
    classifier = TaskFamilyClassifier()
    snapshots = [
        TaskSnapshot(
            uuid="parent-1",
            kind="job",
            state="started",
            root_id="parent-1",
            first_seen_at="2026-03-19T00:00:01+00:00",
        ),
        TaskSnapshot(
            uuid="child-queued",
            kind="callback",
            state="sent",
            root_id="parent-1",
            parent_id="parent-1",
            first_seen_at="2026-03-19T00:00:02+00:00",
        ),
    ]

    families = classifier.build_families(snapshots)

    assert len(families) == 1
    assert families[0].root.uuid == "parent-1"
    assert [item.uuid for item in families[0].items] == ["parent-1"]

    counts = build_section_counts(snapshots)

    assert counts.running_families == 1
    assert counts.queued_families == 0


def test_family_classifier_keeps_unknown_top_level_tasks_visible() -> None:
    classifier = TaskFamilyClassifier()
    snapshots = [
        TaskSnapshot(
            uuid="native-top-level",
            kind="unknown",
            state="succeeded",
            root_id="native-top-level",
            first_seen_at="2026-03-19T00:00:01+00:00",
        )
    ]

    families = classifier.build_families(snapshots)

    assert len(families) == 1
    assert families[0].root.uuid == "native-top-level"
