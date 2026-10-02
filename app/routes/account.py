from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import AccountUpdateRequest
from .auth import format_user_response

router = APIRouter(prefix="/api/account", tags=["Account"])


@router.put("")
@router.put("/")
async def update_account(
    body: AccountUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.name is not None:
        clean_name = body.name.strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="Name cannot be empty.")
        current_user.name = clean_name

    if body.phone is not None:
        current_user.phone = body.phone.strip()

    if body.address is not None:
        current_user.address = body.address.strip()

    db.commit()
    db.refresh(current_user)
    return {"user": format_user_response(current_user)}
