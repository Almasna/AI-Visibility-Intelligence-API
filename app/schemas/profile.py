from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.domains import normalize_domain


class ProfileCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=500)
    industry: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    competitors: list[str] = Field(default_factory=list, max_length=25)

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return normalize_domain(value)

    @field_validator("competitors")
    @classmethod
    def normalize_competitors(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            domain = normalize_domain(value)
            if domain not in seen:
                normalized.append(domain)
                seen.add(domain)
        return normalized

    @model_validator(mode="after")
    def target_not_competitor(self) -> "ProfileCreate":
        if self.domain in self.competitors:
            raise ValueError("The target domain cannot also be a competitor.")
        return self


class ProfileCreatedResponse(BaseModel):
    profile_uuid: str
    name: str
    domain: str
    status: str
    created_at: str


class ProfileResponse(ProfileCreatedResponse):
    industry: str
    description: str
    competitors: list[str]
    updated_at: str
    summary: dict[str, Any]
