from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import AgentPersona


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    agent_persona: AgentPersona

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    agent_persona: AgentPersona | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


class AuthResponse(TokenPair):
    user: UserOut
