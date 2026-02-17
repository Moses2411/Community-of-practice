from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from db.database import get_db
from model import Course, Tutor, TutorialSchedule, Review
from schemas import CourseResponse, TutorialScheduleResponse
from auth.OAuth2 import get_current_tutor
from typing import List

router = APIRouter(
    prefix="/tutor", tags=["Tutor"])

@router.get("/assigned_courses", response_model=List[dict])
def get_my_assigned_courses(db: Session = Depends(get_db), loggedin: Tutor = Depends(get_current_tutor)):

    assigned_schedules = db.query(TutorialSchedule).filter(TutorialSchedule.tutor_id == loggedin.id, TutorialSchedule.is_finalized == True).all()
    
    if not assigned_schedules:
        return []
    
    courses_list = []
    for schedule in assigned_schedules:
        course = db.query(Course).filter(Course.id == schedule.course_id).first()
        
        if course:
        
            courses_list.append({
                "schedule_id": schedule.id,
                "course_title": course,
                "day": schedule.scheduled_day,
                "time": schedule.scheduled_time,
                "venue": schedule.scheduled_venue,
                "total_votes": schedule.total_votes,
                "finalized_at": schedule.finalized_at,
                "is_finalized": schedule.is_finalized
            })
        
    return courses_list

@router.get("/{tutor_id}/assignments", response_model=List[dict])
def get_tutor_assignments_by_id(tutor_id: int, db: Session = Depends(get_db)):
    tutor = db.query(Tutor).filter(Tutor.id == tutor_id).first()
    if not tutor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tutor with ID {tutor_id} not found"
        )
    
    assigned_schedules = db.query(TutorialSchedule).filter(TutorialSchedule.tutor_id == tutor_id, TutorialSchedule.is_finalized == True
    ).options(joinedload(TutorialSchedule.course)).all()
    
    if not assigned_schedules:
        return []
    
    courses_list = []
    for schedule in assigned_schedules:
        course = schedule.course
        
        courses_list.append({
            "tutor_id": tutor_id,
            "tutor_name": tutor.username,
            "schedule_id": schedule.id,
            "course_title": course,
            "day": schedule.scheduled_day,
            "time": schedule.scheduled_time,
            "venue": schedule.scheduled_venue,
            "total_votes": schedule.total_votes,
            "finalized_at": schedule.finalized_at,
            "is_finalized": schedule.is_finalized
        })
    
    return courses_list

@router.get("/all_tutors", response_model=List[dict])
def get_all_tutors(db: Session = Depends(get_db)):
    tutors = db.query(Tutor).all()
    if not tutors:
        raise HTTPException(status_code=404, detail='No registered tutor on the platform')
    return [
        {
            "id": tutor.id,
            "username": tutor.username,
            "email": tutor.email,
            "specialty": tutor.specialty,
            "department": tutor.department
        }
        for tutor in tutors
    ]

@router.get('/reviews/{tutor_id}', response_model=List[dict])
def get_tutor_reviews(tutor_id: int, db: Session = Depends(get_db)):
    tutor_review = db.query(Review).filter(Review.tutor_id == tutor_id).all()
    if not tutor_review:
        raise HTTPException(status_code=404, detail=f"tutor with id {tutor_id} does not have any reviews yet")
    return[
        {
            "review_id": review.id,
            "comment": review.comment,
            "rating": review.rating,
            "student_id": review.student_id
        }
        for review in tutor_review
    ]

@router.delete('/delete/{tutor_id}')
def delete_tutor_account(tutor_id: int, db: Session = Depends(get_db), loggedIn: Tutor = Depends(get_current_tutor)):
    tutor = db.query(Tutor).filter(Tutor.id == tutor_id).first()

    if not tutor:
        raise HTTPException(status_code=404, detail=f"Tutor with id {tutor_id} not found")
    if tutor.id != loggedIn.id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="You are not authorized to delete this account")
    
    db.delete(tutor)
    db.commit()
    return {f"{tutor.username} successfully"}