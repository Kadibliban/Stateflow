"""
StateFlow API v1 Router

Main API router combining all route modules.
"""
from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    organizations,
    workflows,
    executions,
    workers,
    monitoring,
    events,
)

api_router = APIRouter()

# Authentication routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Organization routes
api_router.include_router(organizations.router, prefix="/organizations", tags=["Organizations"])

# Workflow routes
api_router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])

# Execution routes
api_router.include_router(executions.router, prefix="/executions", tags=["Executions"])

# Event routes
api_router.include_router(events.router, prefix="/executions", tags=["Events"])

# Worker routes
api_router.include_router(workers.router, prefix="/workers", tags=["Workers"])

# Monitoring routes
api_router.include_router(monitoring.router, prefix="/metrics", tags=["Monitoring"])