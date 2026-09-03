from httpx import AsyncClient

from app.models.project import Project


async def _create_task(client: AsyncClient, project_id, **overrides) -> dict:
    payload = {"title": "Task"} | overrides
    resp = await client.post(f"/api/v1/projects/{project_id}/tasks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_positions_strictly_increase_on_create(client_a: AsyncClient, project_a: Project):
    t1 = await _create_task(client_a, project_a.id, title="One")
    t2 = await _create_task(client_a, project_a.id, title="Two")
    t3 = await _create_task(client_a, project_a.id, title="Three")

    assert t1["position"] < t2["position"] < t3["position"]


async def test_reorder_rewrites_positions_from_the_given_order(client_a: AsyncClient, project_a: Project):
    t1 = await _create_task(client_a, project_a.id, title="One")
    t2 = await _create_task(client_a, project_a.id, title="Two")
    t3 = await _create_task(client_a, project_a.id, title="Three")

    resp = await client_a.post(
        f"/api/v1/projects/{project_a.id}/tasks/reorder",
        json={"status": "todo", "task_ids": [t3["id"], t1["id"], t2["id"]]},
    )
    assert resp.status_code == 200

    listed = await client_a.get(f"/api/v1/projects/{project_a.id}/tasks?sort=position&order=asc")
    ids_in_order = [item["id"] for item in listed.json()["items"]]
    assert ids_in_order == [t3["id"], t1["id"], t2["id"]]


async def test_status_change_appends_at_end_of_target_column_not_stale_index(
    client_a: AsyncClient, project_a: Project
):
    # Two tasks already sitting in the "done" column ahead of the one we're about to move.
    done_1 = await _create_task(client_a, project_a.id, title="Already done 1", status="done")
    done_2 = await _create_task(client_a, project_a.id, title="Already done 2", status="done")
    todo = await _create_task(client_a, project_a.id, title="Moving to done")

    resp = await client_a.patch(f"/api/v1/tasks/{todo['id']}", json={"status": "done"})
    assert resp.status_code == 200
    moved = resp.json()

    # It must land AFTER both existing done tasks — not keep whatever stale position it
    # had in "todo" (which, being the first task created, was the smallest of the three).
    assert moved["position"] > done_1["position"]
    assert moved["position"] > done_2["position"]


async def test_status_done_sets_and_clears_completed_at(client_a: AsyncClient, project_a: Project):
    task = await _create_task(client_a, project_a.id)
    assert task["completed_at"] is None

    done = (await client_a.patch(f"/api/v1/tasks/{task['id']}", json={"status": "done"})).json()
    assert done["completed_at"] is not None

    back_to_todo = (await client_a.patch(f"/api/v1/tasks/{task['id']}", json={"status": "todo"})).json()
    assert back_to_todo["completed_at"] is None


async def test_list_pagination_total_correct_with_two_filters_active(client_a: AsyncClient, project_a: Project):
    await _create_task(client_a, project_a.id, title="A high", priority="high", status="todo")
    await _create_task(client_a, project_a.id, title="B high", priority="high", status="todo")
    await _create_task(client_a, project_a.id, title="C high done", priority="high", status="done")
    await _create_task(client_a, project_a.id, title="D low", priority="low", status="todo")

    resp = await client_a.get(
        f"/api/v1/projects/{project_a.id}/tasks?status=todo&priority=high&page=1&page_size=1"
    )
    assert resp.status_code == 200
    body = resp.json()
    # Two rows match (todo, high) even though page_size=1 only returns one item — total
    # must reflect the full filtered count, not just what's on this page.
    assert body["total"] == 2
    assert len(body["items"]) == 1
