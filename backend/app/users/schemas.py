from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UpdateProfileRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UpdateEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=EMAIL_PATTERN)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class QuotaResponse(BaseModel):
    quota_bytes: int
    used_bytes: int
    available_bytes: int
    used_percent: float
