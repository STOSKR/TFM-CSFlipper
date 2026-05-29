"""Shared Pydantic configuration for public contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    """Base model for versioned contracts."""

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )
