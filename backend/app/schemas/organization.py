"""
StateFlow Organization Schemas

Pydantic models for organization and membership management.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationBase(BaseModel):
    """Base organization schema."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class OrganizationCreate(OrganizationBase):
    """Organization creation request."""
    pass


class OrganizationUpdate(BaseModel):
    """Organization update request."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = Field(None, pattern="^(active|inactive|suspended)$")


class OrganizationResponse(OrganizationBase):
    """Organization response schema."""
    id: UUID
    status: str
    settings: dict
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    class Config:
        from_attributes = True


class MemberInvite(BaseModel):
    """Member invitation request."""
    email: str = Field(..., description="User email to invite")
    role_name: str = Field(..., pattern="^(owner|administrator|developer|viewer)$")


class MemberUpdate(BaseModel):
    """Member update request."""
    role_name: Optional[str] = Field(None, pattern="^(owner|administrator|developer|viewer)$")
    is_active: Optional[bool] = None


class MemberResponse(BaseModel):
    """Member response schema."""
    id: UUID
    organization_id: UUID
    user_id: UUID
    role_id: UUID
    role_name: str
    joined_at: datetime
    invited_by: Optional[UUID]
    is_active: bool
    user_email: str
    user_username: str
    user_full_name: Optional[str]

    class Config:
        from_attributes = True