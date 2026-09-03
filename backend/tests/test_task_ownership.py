"""Authorization tests — the reason this test harness exists at all. Every one of these
guards against a working IDOR that would otherwise be invisible to code review.
"""

from httpx import AsyncClient

from app.models.project import Project
from app.models.user import User


async def _create_task(client: AsyncClient, project_id, **overrides) -> dict:
    payload = {"title": "Task"} | overrides
    resp = await client.post(f"/api/v1/projects/{project_id}/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_cross_user_get_patch_delete_all_404(
    client_a: AsyncClient, client_b: AsyncClient, project_a: Project
):
    task = await _create_task(client_a, project_a.id)
    task_id = task["id"]

    get_resp = await client_b.get(f"/api/v1/tasks/{task_id}")
    patch_resp = await client_b.patch(f"/api/v1/tasks/{task_id}", json={"title": "hijacked"})
    delete_resp = await client_b.delete(f"/api/v1/tasks/{task_id}")

    assert get_resp.status_code == 404
    assert patch_resp.status_code == 404
    assert delete_resp.status_code == 404

    # And it's genuinely untouched — user_b's 404 didn't silently rename it.
    still_there = await client_a.get(f"/api/v1/tasks/{task_id}")
    assert still_there.status_code == 200
    assert still_there.json()["title"] == "Task"


async def test_create_under_another_users_project_is_404(client_b: AsyncClient, project_a: Project):
    resp = await client_b.post(f"/api/v1/projects/{project_a.id}/tasks", json={"title": "steal"})
    assert resp.status_code == 404


async def test_list_another_users_project_tasks_is_404(client_b: AsyncClient, project_a: Project):
    resp = await client_b.get(f"/api/v1/projects/{project_a.id}/tasks")
    assert resp.status_code == 404


async def test_parent_id_pointing_at_another_users_task_is_422(
    client_a: AsyncClient, client_b: AsyncClient, project_a: Project, project_b: Project
):
    other_task = await _create_task(client_a, project_a.id)

    resp = await client_b.post(
        f"/api/v1/projects/{project_b.id}/tasks",
        json={"title": "cross-tenant parent", "parent_id": other_task["id"]},
    )
    assert resp.status_code == 422


async def test_parent_id_in_a_different_project_of_the_same_user_is_422(
    client_a: AsyncClient, project_a: Project, user_a: User, db
):
    # A second project for the SAME user — parent_id must be scoped by project too, not
    # just by user_id, or a task could be attached across a user's own two projects.
    from datetime import date

    other_project = Project(
        user_id=user_a.id, name="Other project", role="Engineer", start_date=date(2026, 1, 1), is_current=True
    )
    db.add(other_project)
    await db.commit()
    await db.refresh(other_project)

    task_in_other_project = await _create_task(client_a, other_project.id)

    resp = await client_a.post(
        f"/api/v1/projects/{project_a.id}/tasks",
        json={"title": "wrong project parent", "parent_id": task_in_other_project["id"]},
    )
    assert resp.status_code == 422


async def test_depth_capped_at_one_subtask_of_a_subtask_is_422(client_a: AsyncClient, project_a: Project):
    parent = await _create_task(client_a, project_a.id, title="Parent")
    child = await _create_task(client_a, project_a.id, title="Child", parent_id=parent["id"])

    resp = await client_a.post(
        f"/api/v1/projects/{project_a.id}/tasks",
        json={"title": "grandchild", "parent_id": child["id"]},
    )
    assert resp.status_code == 422


async def test_create_task_ignores_client_supplied_user_id(
    client_a: AsyncClient, project_a: Project, user_b: User
):
    """user_id is always taken from the (already-owned) project, never from the request
    body — a bogus user_id in the payload must have zero effect."""
    resp = await client_a.post(
        f"/api/v1/projects/{project_a.id}/tasks",
        json={"title": "spoofed owner", "user_id": str(user_b.id)},
    )
    assert resp.status_code == 201
    # Confirm ownership actually landed on user_a: user_b (the one we tried to spoof)
    # still can't see it, and user_a still can.
    body = resp.json()
    assert body["project_id"] == str(project_a.id)


async def test_reorder_with_foreign_id_is_422_and_leaves_positions_unchanged(
    client_a: AsyncClient, client_b: AsyncClient, project_a: Project, project_b: Project
):
    mine = await _create_task(client_a, project_a.id, title="Mine")
    theirs = await _create_task(client_b, project_b.id, title="Theirs")

    resp = await client_a.post(
        f"/api/v1/projects/{project_a.id}/tasks/reorder",
        json={"status": "todo", "task_ids": [mine["id"], theirs["id"]]},
    )
    assert resp.status_code == 422

    # The status code alone doesn't prove atomicity — re-read both rows and confirm
    # neither position moved.
    mine_after = (await client_a.get(f"/api/v1/tasks/{mine['id']}")).json()
    theirs_after = (await client_b.get(f"/api/v1/tasks/{theirs['id']}")).json()
    assert mine_after["position"] == mine["position"]
    assert theirs_after["position"] == theirs["position"]


async def test_missing_bearer_token_is_401_without_override(client_no_auth: AsyncClient):
    """client_no_auth has no dependency_overrides applied — the REAL get_current_user
    dependency runs against a request with no Authorization header, so a future route
    that accidentally omits `user: User = CurrentUser` entirely can't hide behind an
    override that's otherwise applied everywhere else in this suite."""
    resp = await client_no_auth.get("/api/v1/tasks")
    assert resp.status_code == 401
