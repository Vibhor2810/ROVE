from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import AuthUser, current_member

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/status")
async def auth_status():
    return {
        "mode": "invite_only",
        "jwt_verification": "jwks_or_hs256",
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY),
    }


@router.get("/me")
async def me(user: AuthUser = Depends(current_member)):
    return {"id": user.id, "email": user.email, "member": True}
