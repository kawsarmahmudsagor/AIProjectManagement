from httpx import AsyncClient

from app.models.project import Project


async def test_bulk_create_atomic_zero_rows_on_invalid_item(client_a: AsyncClient, project_a: Project):
    resp = await client_a.post(
        f"/api/v1/projects/{project_a.id}/tasks/bulk",
        json={
            "tasks": [
                {"title": "Valid one"},
                {"title": "Valid two"},
                {"title": ""},  # min_length=1 — this item is invalid
            ]
        },
    )
    assert resp.status_code == 422

    listed = await client_a.get(f"/api/v1/projects/{project_a.id}/tasks")
    assert listed.json()["total"] == 0


async def test_bulk_create_nested_subtasks_get_correct_parent_id(client_a: AsyncClient, project_a: Project):
    resp = await client_a.post(
        f"/api/v1/projects/{project_a.id}/tasks/bulk",
        json={
            "source": "ai",
            "tasks": [
                {
                    "title": "Epic",
                    "subtasks": [{"title": "Child one"}, {"title": "Child two"}],
                }
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["created"] == 3

    items_by_title = {item["title"]: item for item in body["items"]}
    epic = items_by_title["Epic"]
    child_one = items_by_title["Child one"]
    child_two = items_by_title["Child two"]

    assert epic["parent_id"] is None
    assert epic["source"] == "ai"
    assert child_one["parent_id"] == epic["id"]
    assert child_two["parent_id"] == epic["id"]

    # The list endpoint's subtask_total/subtask_done rollup reflects the new children.
    listed = await client_a.get(f"/api/v1/projects/{project_a.id}/tasks")
    epic_row = next(item for item in listed.json()["items"] if item["id"] == epic["id"])
    assert epic_row["subtask_total"] == 2
    assert epic_row["subtask_done"] == 0


async def test_bulk_create_rejects_grandchildren_via_pydantic_shape(client_a: AsyncClient, project_a: Project):
    """TaskSubtaskCreate has no `subtasks` field and forbids extra keys, so a client
    attempting 3-level nesting gets a 422 from request validation before the service
    ever runs — not a silently-dropped grandchild and not a 500."""
    resp = await client_a.post(
        f"/api/v1/projects/{project_a.id}/tasks/bulk",
        json={
            "tasks": [
                {
                    "title": "Epic",
                    "subtasks": [{"title": "Child", "subtasks": [{"title": "Grandchild"}]}],
                }
            ]
        },
    )
    assert resp.status_code == 422
