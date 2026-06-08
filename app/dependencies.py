from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ALGORITHM, CONTENT_ROLES, RESEARCH_ROLES, SECRET_KEY
from db.database import get_db
from model import Membership, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

SessionDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: SessionDep,
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: SessionDep,
) -> User | None:
    if token is None:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        return None
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_researcher(user: CurrentUser) -> User:
    if user.role not in RESEARCH_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Researcher or admin role required.")
    return user


ResearcherUser = Annotated[User, Depends(require_researcher)]


def require_content_manager(user: CurrentUser) -> User:
    if user.role not in CONTENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Facilitator, researcher, or admin role required.",
        )
    return user


ContentManagerUser = Annotated[User, Depends(require_content_manager)]


def require_experimental_group(user: User) -> None:
    if user.role in CONTENT_ROLES:
        return
    if user.study_group == "control":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature is available only to the experimental study group.",
        )


def require_course_membership(db: Session, user: User, course_id: int) -> None:
    if user.role in CONTENT_ROLES:
        return
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.course_id == course_id)
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must join this course first before accessing its content.",
        )
