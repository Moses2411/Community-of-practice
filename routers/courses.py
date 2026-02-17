from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import get_db
from model import Course, Tutor, User
from schemas import CourseCreate, CourseResponse
from auth.OAuth2 import get_current_tutor

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("/", response_model=CourseResponse)
def create_course(request: CourseCreate, db: Session = Depends(get_db), loggedin: Tutor = Depends(get_current_tutor)):
    
    
    existing = db.query(Course).filter((Course.title == request.title) | 
        (Course.course_code == request.course_code)).first()
    
    if existing:
        raise HTTPException(status_code=400, detail=f"Course already exists with title '{existing.title}' and code '{existing.course_code}'")
    
    new_course = Course(
        title=request.title, 
        course_code=request.course_code
    )
    
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    
    return new_course

@router.get("/", response_model=list[CourseResponse])
def list_courses(db: Session = Depends(get_db)):
    return db.query(Course).all()

@router.delete('/delete_course/{course_id}')
def delete_course(course_id: int, db:Session = Depends(get_db), loggedin: Tutor = Depends(get_current_tutor)):
    available1 = db.query(Course).filter(Course.id == course_id).first()
    tutor = db.query(Tutor).filter(Tutor.id == loggedin.id).first()

    if not available1:
        raise HTTPException(status_code=404, detail= 'Course not found')
    if not tutor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detial="only tutors can delete courses")
    db.delete(available1)
    db.commit()

    return {f'{available1.title} deleted successfully by {loggedin.username}'}
