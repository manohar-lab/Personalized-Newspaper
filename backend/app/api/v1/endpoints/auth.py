from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User, UserProfile
from app.schemas.auth import UserRegister, UserLogin, UserResponse, TokenResponse
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account and return JWT access token."""
    normalized_email = user_in.email.strip().lower()

    # Check for existing email
    stmt = select(User).where(User.email == normalized_email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    # Create new user and profile
    new_user = User(
        email=normalized_email,
        password_hash=hash_password(user_in.password),
        full_name=user_in.full_name,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    new_profile = UserProfile(
        user_id=new_user.id,
        display_name=user_in.full_name or normalized_email.split("@")[0],
    )
    db.add(new_profile)
    await db.commit()

    # Re-fetch user with profile loaded
    stmt_user = select(User).options(selectinload(User.profile)).where(User.id == new_user.id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one()

    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user with email and password, returning JWT access token."""
    normalized_email = credentials.email.strip().lower()

    stmt = select(User).options(selectinload(User.profile)).where(User.email == normalized_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive",
        )

    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get authenticated user details."""
    return UserResponse.model_validate(current_user)
