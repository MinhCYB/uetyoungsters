"""Provisioning router — tenant and bulk user setup.

Routes use full paths (no shared prefix), mounted directly in main.py.
Skeleton only — business logic to be implemented separately.
"""

from fastapi import APIRouter

router = APIRouter(tags=["provisioning"])


@router.post("/api/provisioning/tenants")
def create_tenant():
    """Create a new tenant (school/organization). TODO: implement."""
    return {"status": "not_implemented"}


@router.post("/api/provisioning/tenants/{tenant_id}/invite")
def invite_users(tenant_id: str):
    """Send batch invitations for a tenant. TODO: implement."""
    return {"status": "not_implemented", "tenant_id": tenant_id}


@router.post("/api/provisioning/tenants/{tenant_id}/classes")
def create_class(tenant_id: str):
    """Create a school class within a tenant. TODO: implement."""
    return {"status": "not_implemented", "tenant_id": tenant_id}
