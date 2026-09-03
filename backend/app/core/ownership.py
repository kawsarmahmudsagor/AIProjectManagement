"""The one place a per-user-scoped row is looked up and ownership-checked.

Every table in this schema that belongs to a user carries its own `user_id` column, so
"is this mine" is always a SQL predicate, never a post-fetch Python comparison. Before
this module existed, that check was reinvented ad hoc four times — `_get_owned_project`
in routers/projects.py, `_get_owned_session` in services/chat_service.py, an inline
`job.user_id != user.id` in routers/jobs.py, and a `None`-returning variant in
suggestion_service — each raising something slightly different. `require_owned` is the
one version every new resource (starting with Task) should use instead.

This lives in `core/`, not `deps.py`, because services must be able to call it too (SAQ
background jobs call the same service functions the routers do — see backend/DESIGN.md
§1/§6) and a service has no business raising `HTTPException`. `ResourceNotFoundError` is
mapped to a 404 by the app-wide handler registered in app/main.py instead.

Every existing router already returns 404 (not 403) for a row that exists but belongs to
someone else, which keeps ids non-enumerable — do not "improve" this to 403.
"""

from typing import Any, Protocol, TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession


class _UserOwned(Protocol):
    """Structural shape every model passed to owned()/require_owned() must have. Not
    meant to be instantiated — SQLAlchemy declarative classes satisfy this shape via
    their `Mapped[...]` column descriptors without inheriting from it explicitly."""

    id: Any
    user_id: Any


M = TypeVar("M", bound=_UserOwned)


class ResourceNotFoundError(Exception):
    """One exception for both "doesn't exist" and "exists but isn't yours" — the two
    cases every caller here already treats identically. Subclass this (see
    ChatSessionNotFoundError) when an existing call site needs to keep catching its own
    specific type; the app-wide handler still catches it via the exception's MRO."""

    def __init__(self, resource: str, resource_id: UUID | str | None = None):
        self.resource = resource
        self.resource_id = resource_id
        detail = f"{resource} not found"
        if resource_id is not None:
            detail += f" ({resource_id})"
        super().__init__(detail)


def owned(model: type[M], user_id: UUID) -> Select:
    """The one place a user-scoped query is built. If ownership ever becomes shared
    (a team, an org) instead of strictly per-user, this is the only function that
    changes — every call site stays the same."""
    return select(model).where(model.user_id == user_id)


async def require_owned(
    db: AsyncSession,
    model: type[M],
    obj_id: UUID,
    user_id: UUID,
    *,
    resource: str | None = None,
) -> M:
    """Fetch a row scoped by both id and user_id in one query — never `db.get()` followed
    by a Python `if row.user_id != user_id` check, which is correct today but is the
    version that silently survives a copy-paste with the check dropped."""
    stmt = owned(model, user_id).where(model.id == obj_id)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise ResourceNotFoundError(resource or model.__name__, obj_id)
    return row
