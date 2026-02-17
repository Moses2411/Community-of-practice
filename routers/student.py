from fastapi import APIRouter, status, HTTPException, Depends
from model import User
from schemas import UserResponse
from sqlalchemy.orm import Session
from db.database import get_db
from auth.OAuth2 import get_current_student
from typing import Dict, List

router = APIRouter(prefix='/student', tags=['student'])

@router.get('/all_students', response_model=List[Dict])
def get_all_resistered_students(db: Session = Depends(get_db)):
    student = db.query(User).all()
    if not student:
        raise HTTPException(status_code=404, detail= "No student found in the database")
    return[{

        'username': s.username,
        'program': s.program,
        'email': s.email
    }
    for s in student
    ]

@router.get('id_student/{student_id}', response_model= UserResponse)
def get_user_by_id(student_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == student_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Invalid student_id')
    return user
     