from pydantic import BaseModel, Field


class UpdateProfileRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)


class QuotaResponse(BaseModel):
    quota_bytes: int
    used_bytes: int
    available_bytes: int
    used_percent: float
