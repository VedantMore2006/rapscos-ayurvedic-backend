from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..auth import (
    ADMIN_INVITE_CODE,
    create_access_token,
    get_current_user,
    get_current_user_optional,
    hash_password,
    timing_safe_response,
    verify_dummy,
    verify_password,
)
from ..database import get_db
from ..limiter import limiter
from ..models import User
from ..schemas import (
    LoginRequest,
    PasswordChangeRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def format_user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "phone": user.phone or "",
        "address": user.address or "",
        "role": user.role,
        "created_at": user.created_at,
    }


@router.post("/signup", response_model=TokenResponse)
@limiter.limit("8/15minutes")
async def signup(
    request: Request,
    response: Response,
    body: SignupRequest,
    db: Session = Depends(get_db),
):
    async def _do_signup():
        clean_email = body.email.strip().lower()
        existing = db.query(User).filter(User.email == clean_email).first()
        if existing:
            # Constant dummy work so timing doesn't leak exist vs new
            verify_dummy(body.password)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists. Please log in.",
            )

        # Check invite code for admin role
        is_admin_code = False
        if body.code and body.code.strip():
            if body.code.strip().upper() == ADMIN_INVITE_CODE.upper():
                is_admin_code = True
            else:
                verify_dummy(body.password)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="The invite code is not correct.",
                )

        role = "owner" if is_admin_code else "customer"
        hashed = hash_password(body.password)

        new_user = User(
            email=clean_email,
            hashed_password=hashed,
            name=body.name.strip(),
            phone=(body.phone or "").strip(),
            role=role,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        token = create_access_token({"sub": str(new_user.id), "role": new_user.role})

        # Set cookie as well for backward compatibility
        response.set_cookie(
            key="rapscos_token",
            value=token,
            max_age=30 * 86400,
            httponly=True,
            samesite="lax",
            secure=False,  # Can be True in HTTPS prod
        )

        return {
            "token": token,
            "user": format_user_response(new_user),
        }

    return await timing_safe_response(_do_signup())


@router.post("/login", response_model=TokenResponse)
@limiter.limit("8/15minutes")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    async def _do_login():
        login_val = body.get_email_or_login()
        user = db.query(User).filter(User.email == login_val).first()

        if user:
            is_valid = verify_password(body.password, user.hashed_password)
            # If user was verified with legacy scrypt, upgrade to Argon2id automatically
            if is_valid and user.hashed_password.startswith("scrypt$"):
                user.hashed_password = hash_password(body.password)
                db.commit()
        else:
            verify_dummy(body.password)
            is_valid = False

        if not is_valid or not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Wrong email or password.",
            )

        token = create_access_token({"sub": str(user.id), "role": user.role})

        response.set_cookie(
            key="rapscos_token",
            value=token,
            max_age=30 * 86400,
            httponly=True,
            samesite="lax",
            secure=False,
        )

        return {
            "token": token,
            "user": format_user_response(user),
        }

    return await timing_safe_response(_do_login())


@router.get("/me")
async def get_me(
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Returns current user info. If not authenticated, returns null user
    without throwing error (mirrors frontend expectance).
    """
    if not current_user:
        return {"user": None}
    return {"user": format_user_response(current_user)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="rapscos_token")
    return {"ok": True}


@router.post("/password")
async def change_password(
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    async def _do_password():
        curr = body.get_current()
        new_pwd = body.get_new()
        if not curr or not new_pwd:
            raise HTTPException(status_code=400, detail="Current and new password are required.")
        if len(new_pwd) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

        if not verify_password(curr, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")

        current_user.hashed_password = hash_password(new_pwd)
        db.commit()
        return {"ok": True}

    return await timing_safe_response(_do_password())


# Support for legacy /api/auth?action=... dispatcher
@router.api_route("", methods=["GET", "POST"])
async def auth_dispatcher(
    request: Request,
    response: Response,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    action = action or request.query_params.get("action")
    if request.method == "GET" and action == "me":
        return await get_me(current_user=current_user)

    if request.method == "POST":
        body_json = await request.json()
        if action == "login":
            return await login(request, response, LoginRequest(**body_json), db)
        elif action == "signup":
            return await signup(request, response, SignupRequest(**body_json), db)
        elif action == "logout":
            return await logout(response)
        elif action == "password":
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required.")
            return await change_password(PasswordChangeRequest(**body_json), current_user, db)

    raise HTTPException(status_code=400, detail=f"Unknown or unsupported auth action: {action}")
