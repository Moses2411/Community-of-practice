from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import get_db
from auth.hashing import Hash
from model import User, Tutor
from auth.OAuth2 import create_access_token
from schemas import UserCreate, Login, UserResponse, TutorCreate, TutorResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/student_signup", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    existing_tutor = db.query(Tutor).filter(Tutor.email == user.email).first()
    if existing_user or existing_tutor:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        username=user.username,
        email=user.email,
        password=Hash.hash_password(user.password),
        program=user.program,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post('/tutor_signup', response_model=TutorResponse)
def register_tutor(tutor: TutorCreate, db:Session = Depends(get_db)):
    existing_tutor = db.query(Tutor).filter(Tutor.email == tutor.email).first()
    existing_tutor2 = db.query(User).filter(User.email == tutor.email).first()
    if existing_tutor or existing_tutor2:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="email already exist")
    new_tutor = Tutor(
        email = tutor.email,
        username = tutor.username,
        password = Hash.hash_password(tutor.password),
        specialty = tutor.specialty,
        department = tutor.department
    )

    db.add(new_tutor)
    db.commit()
    db.refresh(new_tutor)
    return new_tutor


@router.post("/login")
def login(request: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    tutor = db.query(Tutor).filter(Tutor.email == request.email).first()

    if user:
        if not Hash.verify(user.password, request.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid password')
        token = create_access_token(data={"sub": str(user.id), "role": "student"})
        role = "student"
        user_data = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
        }

    elif tutor:
        if not Hash.verify(tutor.password, request.password):
            raise HTTPException(status_code=401, detail="Invalid password")
        
        token = create_access_token(data={"sub": str(tutor.id), "role": "tutor"})
        role = "tutor"
        user_data = {
            "id": tutor.id,
            "email": tutor.email,
            "username": tutor.username,
            "specialty": tutor.specialty,
            "department": tutor.department
        }

    else:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "user": user_data
    }