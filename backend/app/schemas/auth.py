from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import AgentPersona, ChatProvider


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Only first_name is required — middle/last/preferred name are all filled in later on
    # the Profile page (see routers/profile.py), never forced at signup.
    first_name: str = Field(min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    preferred_name: str | None = Field(default=None, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    agent_persona: AgentPersona
    first_name: str
    middle_name: str | None
    last_name: str | None
    preferred_name: str | None
    chat_provider: ChatProvider
    chatbot_preemptive_github_suggestions: bool

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    agent_persona: AgentPersona | None = None
    chat_provider: ChatProvider | None = None
    chatbot_preemptive_github_suggestions: bool | None = None
    # Name fields are also editable here as a convenience for the /auth/me caller, even
    # though the Profile page's own PATCH /profile is the primary place they're edited
    # (see schemas/profile.py) — both paths write the same User columns.
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    preferred_name: str | None = Field(default=None, max_length=80)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


class AuthResponse(TokenPair):
    user: UserOut
