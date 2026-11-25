"""
StateFlow Organization Routes

Organization CRUD and membership management.
"""
from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.security import get_password_hash
from app.models.organization import Organization, OrganizationMember, MemberRole, OrganizationStatus
from app.models.user import User, Role
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    MemberInvite,
    MemberResponse,
    MemberUpdate,
)
from app.api.v1.routes.auth import get_current_user

router = APIRouter()


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    request: OrganizationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationResponse:
    """Create a new organization."""
    # Check if slug is taken
    existing = await session.execute(
        select(Organization).where(Organization.slug == request.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already taken",
        )

    # Create organization
    org = Organization(
        name=request.name,
        slug=request.slug,
        description=request.description,
        status=OrganizationStatus.ACTIVE,
    )
    session.add(org)
    await session.flush()

    # Add creator as owner
    owner_role = await session.execute(
        select(Role).where(Role.name == "owner")
    )
    owner_role = owner_role.scalar_one_or_none()
    if not owner_role:
        # Create system roles if they don't exist
        owner_role = Role(name="owner", display_name="Owner", description="Organization owner", is_system=True)
        admin_role = Role(name="administrator", display_name="Administrator", description="Organization administrator", is_system=True)
        dev_role = Role(name="developer", display_name="Developer", description="Organization developer", is_system=True)
        viewer_role = Role(name="viewer", display_name="Viewer", description="Organization viewer", is_system=True)
        session.add_all([owner_role, admin_role, dev_role, viewer_role])
        await session.flush()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role_id=owner_role.id,
        role_name=MemberRole.OWNER,
        is_active=True,
    )
    session.add(member)
    await session.commit()
    await session.refresh(org)

    return OrganizationResponse.model_validate(org)


@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> List[OrganizationResponse]:
    """List organizations user is a member of."""
    # Get user's organization memberships
    memberships = await session.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == current_user.id, OrganizationMember.is_active == True)
        .options(selectinload(OrganizationMember.organization))
        .offset(skip)
        .limit(limit)
    )
    memberships = memberships.scalars().all()

    orgs = [m.organization for m in memberships if m.organization.status != OrganizationStatus.DELETED]
    return [OrganizationResponse.model_validate(org) for org in orgs]


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationResponse:
    """Get organization by ID."""
    # Check membership
    membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
        )
    )
    membership = membership.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    org = await session.get(Organization, org_id)
    if not org or org.status == OrganizationStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return OrganizationResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    request: OrganizationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationResponse:
    """Update organization."""
    # Check admin/owner permission
    membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
            OrganizationMember.role_name.in_([MemberRole.OWNER, MemberRole.ADMINISTRATOR]),
        )
    )
    membership = membership.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    org = await session.get(Organization, org_id)
    if not org or org.status == OrganizationStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Update fields
    if request.name is not None:
        org.name = request.name
    if request.description is not None:
        org.description = request.description
    if request.status is not None:
        org.status = OrganizationStatus(request.status)

    await session.commit()
    await session.refresh(org)

    return OrganizationResponse.model_validate(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete organization (soft delete)."""
    # Check owner permission
    membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
            OrganizationMember.role_name == MemberRole.OWNER,
        )
    )
    membership = membership.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner can delete organization",
        )

    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    org.status = OrganizationStatus.DELETED
    org.deleted_at = datetime.now(timezone.utc)
    await session.commit()


# Member management
@router.post("/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    org_id: UUID,
    request: MemberInvite,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemberResponse:
    """Invite a member to organization."""
    # Check admin/owner permission
    membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
            OrganizationMember.role_name.in_([MemberRole.OWNER, MemberRole.ADMINISTRATOR]),
        )
    )
    membership = membership.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    # Find user by email
    user = await session.execute(
        select(User).where(User.email == request.email)
    )
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if already a member
    existing = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member",
        )

    # Get role
    role = await session.execute(
        select(Role).where(Role.name == request.role_name)
    )
    role = role.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    # Create membership
    member = OrganizationMember(
        organization_id=org_id,
        user_id=user.id,
        role_id=role.id,
        role_name=MemberRole(request.role_name),
        invited_by=current_user.id,
        is_active=True,
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)

    # Load relationships for response
    await session.refresh(member, ["user", "role"])
    return MemberResponse(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        role_id=member.role_id,
        role_name=member.role_name.value,
        joined_at=member.joined_at,
        invited_by=member.invited_by,
        is_active=member.is_active,
        user_email=member.user.email,
        user_username=member.user.username,
        user_full_name=member.user.full_name,
    )


@router.get("/{org_id}/members", response_model=List[MemberResponse])
async def list_members(
    org_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> List[MemberResponse]:
    """List organization members."""
    # Check membership
    membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    members = await session.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == org_id)
        .options(selectinload(OrganizationMember.user), selectinload(OrganizationMember.role))
        .offset(skip)
        .limit(limit)
    )
    members = members.scalars().all()

    return [
        MemberResponse(
            id=m.id,
            organization_id=m.organization_id,
            user_id=m.user_id,
            role_id=m.role_id,
            role_name=m.role_name.value,
            joined_at=m.joined_at,
            invited_by=m.invited_by,
            is_active=m.is_active,
            user_email=m.user.email,
            user_username=m.user.username,
            user_full_name=m.user.full_name,
        )
        for m in members
    ]


@router.patch("/{org_id}/members/{member_id}", response_model=MemberResponse)
async def update_member(
    org_id: UUID,
    member_id: UUID,
    request: MemberUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemberResponse:
    """Update member role or status."""
    # Check owner permission (only owner can change roles)
    membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
            OrganizationMember.role_name == MemberRole.OWNER,
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner can update members",
        )

    member = await session.get(OrganizationMember, member_id)
    if not member or member.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # Prevent owner from removing themselves
    if member.user_id == current_user.id and request.role_name and request.role_name != "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner cannot change their own role",
        )

    if request.role_name is not None:
        role = await session.execute(
            select(Role).where(Role.name == request.role_name)
        )
        role = role.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role",
            )
        member.role_id = role.id
        member.role_name = MemberRole(request.role_name)

    if request.is_active is not None:
        member.is_active = request.is_active

    await session.commit()
    await session.refresh(member, ["user", "role"])

    return MemberResponse(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        role_id=member.role_id,
        role_name=member.role_name.value,
        joined_at=member.joined_at,
        invited_by=member.invited_by,
        is_active=member.is_active,
        user_email=member.user.email,
        user_username=member.user.username,
        user_full_name=member.user.full_name,
    )


@router.delete("/{org_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: UUID,
    member_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Remove member from organization."""
    # Check owner permission
    membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.is_active == True,
            OrganizationMember.role_name == MemberRole.OWNER,
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owner can remove members",
        )

    member = await session.get(OrganizationMember, member_id)
    if not member or member.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # Prevent owner from removing themselves
    if member.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner cannot remove themselves",
        )

    await session.delete(member)
    await session.commit()


# Import timezone for datetime
from datetime import datetime, timezone