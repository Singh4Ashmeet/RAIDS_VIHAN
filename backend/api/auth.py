"""JWT authentication routes and dependencies for RAID Nexus."""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

try:
    from config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
    from database import fetch_one
    from security import limiter
except ModuleNotFoundError:
    from backend.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
    from backend.database import fetch_one
    from backend.security import limiter

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str


class TokenData(BaseModel):
    username: str | None = None
    role: str | None = None


def verify_password(plain: str, hashed: str) -> bool:
    """Return whether a plaintext password matches a stored bcrypt hash."""

    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""

    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token with subject, role, and expiry claims."""

    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(user)
    sanitized.pop("hashed_password", None)
    return sanitized


@router.post("/auth/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()) -> Token:
    """Authenticate a user and issue a bearer token."""

    _ = request
    username = form_data.username.strip()
    user = await fetch_one("users", username, id_field="username")
    if user is None or not verify_password(form_data.password, str(user["hashed_password"])):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account disabled")

    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=str(user["role"]),
        username=str(user["username"]),
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Decode the current bearer token and return the active database user."""

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenData(
            username=payload.get("sub"),
            role=payload.get("role"),
        )
    except JWTError as exc:
        raise _auth_error() from exc

    if token_data.username is None:
        raise _auth_error()

    user = await fetch_one("users", token_data.username, id_field="username")
    if user is None or not user.get("is_active"):
        raise _auth_error()
    return _public_user(user)


async def verify_ws_token(token: str | None) -> dict[str, Any] | None:
    """Validate an optional websocket token and return the active user or None."""

    if token is None:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

    username = payload.get("sub")
    if not username:
        return None

    user = await fetch_one("users", username, id_field="username")
    if user is None or not user.get("is_active"):
        return None
    return _public_user(user)


async def get_current_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Require the current user to have the admin role."""

    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def get_current_any_user(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Return any authenticated active user."""

    return user


@router.get("/auth/me")
async def me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Return the current authenticated user's public profile."""

    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
        "full_name": current_user.get("full_name"),
    }
