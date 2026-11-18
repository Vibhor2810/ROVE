from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import AuthUser, current_user
from app.database.client import rpc

router = APIRouter(prefix="/api/invitations", tags=["Invitations"])


class CodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9\-_]+$")


@router.post("/validate")
async def validate(body: CodeIn):
    """Public: lets the sign-up form check a code before creating an account.
    Returns only valid/invalid, never who issued it."""
    ok = await rpc("rove_validate_invite", None, {"p_code": body.code})
    return {"valid": bool(ok)}


@router.post("/redeem")
async def redeem(body: CodeIn, user: AuthUser = Depends(current_user)):
    """Authenticated (not yet member): consumes the code and grants membership.
    The atomic check-and-consume happens in a SECURITY DEFINER SQL function."""
    ok = await rpc("rove_redeem_invite", user.token, {"p_code": body.code})
    if not ok:
        raise HTTPException(status_code=403, detail="Invalid or already used invitation")
    return {"member": True}
