"""accept_breakdown_items() is the highest-severity correctness surface in Feature 2: a
double-submit or a refresh mid-accept must never create duplicate tasks, a subtask must
never attach under something that isn't a genuine top-level task (depth stays capped at
1), and dry_run must never persist anything — see services/breakdown_service.py's
docstring.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.ai_provider_setting import ProviderName
from app.models.breakdown_job import BreakdownJob
from app.models.extraction_job import JobStatus
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.breakdown import BreakdownAcceptItem
from app.services.breakdown_service import accept_breakdown_items, dismiss_breakdown_refs


async def _make_job(db, user: User, project: Project, **overrides) -> BreakdownJob:
    job = BreakdownJob(
        user_id=user.id, project_id=project.id, provider=ProviderName.GEMINI, prompt="test", **overrides
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def test_accept_creates_top_level_and_child_in_one_batch(db, user_a: User, project_a: Project):
    job = await _make_job(db, user_a, project_a)
    items = [
        BreakdownAcceptItem(ref="parent", title="Epic"),
        BreakdownAcceptItem(ref="child", title="Subtask", parent_ref="parent"),
    ]
    created, skipped, promoted = await accept_breakdown_items(db, user_a.id, project_a, job, items)

    assert not skipped
    assert not promoted
    by_ref = {("parent" if t.parent_id is None else "child"): t for t in created}
    assert by_ref["parent"].parent_id is None
    assert by_ref["child"].parent_id == by_ref["parent"].id


async def test_accept_promotes_child_whose_parent_was_not_selected(db, user_a: User, project_a: Project):
    job = await _make_job(db, user_a, project_a)
    # "orphan" claims a parent_ref that was never submitted in this batch and doesn't
    # exist in job.accepted_refs either — the promotion-warning path, not a rejection.
    items = [BreakdownAcceptItem(ref="orphan", title="Orphaned subtask", parent_ref="never-submitted")]
    created, _skipped, promoted = await accept_breakdown_items(db, user_a.id, project_a, job, items)

    assert len(created) == 1
    assert created[0].parent_id is None
    assert promoted == ["orphan"]


async def test_accept_is_idempotent_on_double_submit(db, user_a: User, project_a: Project):
    job = await _make_job(db, user_a, project_a)
    items = [BreakdownAcceptItem(ref="t1", title="Ship it")]

    first_created, first_skipped, _ = await accept_breakdown_items(db, user_a.id, project_a, job, items)
    assert len(first_created) == 1
    assert not first_skipped

    # Refresh the job the way a second HTTP request would re-fetch it, so
    # job.accepted_refs reflects the commit above.
    await db.refresh(job)
    second_created, second_skipped, _ = await accept_breakdown_items(db, user_a.id, project_a, job, items)

    assert second_created == []
    assert second_skipped == [{"ref": "t1", "reason": "already accepted"}]

    total = (await db.execute(select(Task).where(Task.project_id == project_a.id))).scalars().all()
    assert len(total) == 1  # not two


async def test_accept_resolves_parent_created_in_an_earlier_call(db, user_a: User, project_a: Project):
    """The review UI allows a second pass over unaccepted rows — a later batch's
    parent_ref must resolve against a task created by an earlier batch."""
    job = await _make_job(db, user_a, project_a)
    first, _, _ = await accept_breakdown_items(
        db, user_a.id, project_a, job, [BreakdownAcceptItem(ref="parent", title="Epic")]
    )
    await db.refresh(job)

    second, skipped, promoted = await accept_breakdown_items(
        db, user_a.id, project_a, job, [BreakdownAcceptItem(ref="child", title="Later subtask", parent_ref="parent")]
    )
    assert not skipped
    assert not promoted
    assert second[0].parent_id == first[0].id


async def test_accept_wont_attach_under_a_task_that_already_has_a_parent(db, user_a: User, project_a: Project):
    """Depth is capped at 1 everywhere else in this codebase; accept must enforce it too,
    even across two separate accept calls where the "existing" parent is itself already a
    subtask."""
    job = await _make_job(db, user_a, project_a)
    await accept_breakdown_items(
        db,
        user_a.id,
        project_a,
        job,
        [
            BreakdownAcceptItem(ref="grandparent", title="Epic"),
            BreakdownAcceptItem(ref="parent", title="Subtask", parent_ref="grandparent"),
        ],
    )
    await db.refresh(job)

    created, skipped, promoted = await accept_breakdown_items(
        db,
        user_a.id,
        project_a,
        job,
        [BreakdownAcceptItem(ref="grandchild", title="Would-be 3rd level", parent_ref="parent")],
    )
    assert not skipped
    assert promoted == ["grandchild"]
    assert created[0].parent_id is None


async def test_dry_run_creates_nothing(db, user_a: User, project_a: Project):
    job = await _make_job(db, user_a, project_a)
    created, _skipped, _promoted = await accept_breakdown_items(
        db, user_a.id, project_a, job, [BreakdownAcceptItem(ref="t1", title="Preview only")], dry_run=True
    )
    assert len(created) == 1  # returned for the dry-run preview...
    assert created[0].title == "Preview only"

    rows = (await db.execute(select(Task).where(Task.project_id == project_a.id))).scalars().all()
    assert rows == []  # ...but never actually persisted

    await db.refresh(job)
    assert job.accepted_refs == {}  # and accepted_refs isn't updated either


async def test_dismiss_dedupes_and_persists(db, user_a: User, project_a: Project):
    job = await _make_job(db, user_a, project_a)
    job = await dismiss_breakdown_refs(db, job, ["t1", "t2"])
    job = await dismiss_breakdown_refs(db, job, ["t2", "t3"])
    assert sorted(job.dismissed_refs) == ["t1", "t2", "t3"]


async def test_stale_breakdown_job_is_reaped(db, user_a: User, project_a: Project):
    """The stale-job reaper (generalized in this feature to sweep both job tables) must
    catch a crashed breakdown-job worker exactly like it already does for extraction —
    otherwise a user is left watching a spinner forever with no way to stop it."""
    from app.workers.stale_jobs import reap_stale_jobs

    job = await _make_job(
        db,
        user_a,
        project_a,
        status=JobStatus.EXTRACTING,
        created_at=datetime.now(UTC) - timedelta(minutes=20),
    )

    await reap_stale_jobs(ctx=None)

    await db.refresh(job)
    assert job.status == JobStatus.FAILED
    assert job.error_code == "TIMEOUT"
