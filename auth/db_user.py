from sqlalchemy.orm.session import Session
from auth.hashing import Hash
from model import User, Tutor
from schemas import UserCreate
import random


def create_user(request: UserCreate, db: Session):
    hashed_password = Hash.hash_password(request.password)
    user = User(
        username=request.username,
        email=request.email,
        password=hashed_password,
        program=request.program
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def get_user_by_id(db:Session, id: int):
    return db.query(User).filter(User.id == id).first()

def get_tutor_by_id(db:Session, id: int):
    return db.query(Tutor).filter(Tutor.id == id).first()