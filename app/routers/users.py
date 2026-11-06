"""KTS — Staff management (owner only)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import OWNER, RequestContext, allow
from app.models import User
from app.schemas.auth import UserCreate, UserResponse, UserUpdate
from app.services.auth_service import revoke_all_sessions
from app.utils.scoping import get_owned

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def _to_response(u: User) -> UserResponse:
    return UserResponse(id=str(u.id), name=u.name, phone=u.phone, role=u.role, is_active=u.is_active)


@router.get("", response_model=list[UserResponse])
def list_users(ctx: RequestContext = Depends(allow(*OWNER)), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.business_id == ctx.business_id).order_by(User.name).all()
    return [_to_response(u) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
def invite_user(data: UserCreate, ctx: RequestContext = Depends(allow(*OWNER)), db: Session = Depends(get_db)):
    """Add a staff member. They sign in with this phone number via Firebase."""
    if db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(status_code=409, detail="This phone number already has a KTS account")
    user = User(id=uuid.uuid4(), business_id=ctx.business_id, name=data.name, phone=data.phone, role=data.role)
    db.add(user)
    db.commit()
    return _to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    ctx: RequestContext = Depends(allow(*OWNER)),
    db: Session = Depends(get_db),
):
    user = get_owned(db, User, user_id, ctx)
    changes = data.model_dump(exclude_unset=True)
    if user.id == ctx.user_id and (changes.get("role", "owner") != "owner" or changes.get("is_active") is False):
        raise HTTPException(status_code=400, detail="You cannot demote or disable yourself")

    for key, value in changes.items():
        setattr(user, key, value)
    if changes.get("is_active") is False:
        revoke_all_sessions(db, user)
    db.commit()
    return _to_response(user)
