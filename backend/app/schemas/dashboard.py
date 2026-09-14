from pydantic import BaseModel

from app.schemas.project import ProjectSummary


class TechnologyCount(BaseModel):
    name: str
    project_count: int


class DashboardSummary(BaseModel):
    """The whole dashboard in one response: a skills/technology summary across every
    project, the counts, and the compact project list. No rich project cards — `projects`
    reuses schemas.project.ProjectSummary, which project_service.list_projects already
    returns and which its own docstring calls "deliberately small".

    `technologies` (evidence, derived + counted from saved projects) and
    `primary_skills`/`secondary_skills` (claims, self-declared on the profile) are kept
    as separate fields rather than merged into one list — merging them would make "3
    projects use Postgres" indistinguishable from "I said I know Postgres", exactly the
    distinction a skills summary exists to preserve.
    """

    total_projects: int
    current_projects: int
    technologies: list[TechnologyCount]
    # The true distinct count even when `technologies` was capped by ?top_technologies.
    distinct_technology_count: int
    primary_skills: list[str]
    secondary_skills: list[str]
    projects: list[ProjectSummary]
