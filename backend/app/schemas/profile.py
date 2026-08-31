from pydantic import BaseModel, Field

# Field names accepted by POST /profile/enhance — mirrors providers.prompts.PROFILE_FIELD_OPS'
# keys exactly (services/profile_service.enhance_field looks the op/limit up from there).
ENHANCEABLE_FIELDS = (
    "professional_biography",
    "work_experience_summary",
    "career_objective",
    "key_strengths",
    "responsibilities",
)


class ProfileOut(BaseModel):
    photo_url: str | None = None
    designation: str | None = None
    team: str | None = None
    organization: str | None = None
    speciality: str | None = None
    primary_skills: list[str] = []
    secondary_skills: list[str] = []
    professional_biography: str = ""
    work_experience_summary: str = ""
    career_objective: str = ""
    key_strengths: str = ""
    responsibilities: str = ""
    # Name fields live on User, not UserProfile, but are edited from the same page/form —
    # see routers/profile.py's PATCH /profile, which writes both tables in one call.
    first_name: str
    middle_name: str | None = None
    last_name: str | None = None
    preferred_name: str | None = None


class ProfileUpdate(BaseModel):
    designation: str | None = Field(default=None, max_length=150)
    team: str | None = Field(default=None, max_length=150)
    organization: str | None = Field(default=None, max_length=150)
    speciality: str | None = Field(default=None, max_length=150)
    primary_skills: list[str] | None = None
    secondary_skills: list[str] | None = None
    professional_biography: str | None = Field(default=None, max_length=550)
    work_experience_summary: str | None = Field(default=None, max_length=390)
    career_objective: str | None = Field(default=None, max_length=390)
    key_strengths: str | None = Field(default=None, max_length=390)
    responsibilities: str | None = Field(default=None, max_length=390)

    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    preferred_name: str | None = Field(default=None, max_length=80)


class ProfileEnhanceRequest(BaseModel):
    field: str  # one of ENHANCEABLE_FIELDS
    target_text: str = ""
    instruction: str | None = None


class ProfileEnhanceResponse(BaseModel):
    text: str


class PhotoUploadResponse(BaseModel):
    photo_url: str
