from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from collections import Counter
from typing import Dict, List
from model import (
    StudentSchedulePreference, 
    TutorialSchedule, 
    Course, 
    Tutor, 
    User,
    StudentSchedulePreference,
    TutorialSchedule
)
from schemas import (
    SchedulePreferenceCreate, 
    SchedulePreferenceResponse,
    TutorialScheduleResponse,
    CourseScheduleAggregation
)
from db.database import get_db
from auth.OAuth2 import get_current_user, get_current_student

router = APIRouter(prefix='/schedule', tags=['Schedule'])

@router.post('/submit-preference', response_model=SchedulePreferenceResponse)
def submit_schedule_preference(request: SchedulePreferenceCreate, db: Session = Depends(get_db),loggedin: User = Depends(get_current_user)):
    
    course = db.query(Course).filter(Course.id == request.course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    
    tutor = db.query(Tutor).filter(Tutor.id == request.tutor_id).first()
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found")
    existing_preference = db.query(StudentSchedulePreference).filter(StudentSchedulePreference.student_id == loggedin.id,
        StudentSchedulePreference.course_id == request.course_id
    ).first()
    
    if existing_preference:
        existing_preference.tutor_id = request.tutor_id
        existing_preference.preferred_day = request.preferred_day
        existing_preference.preferred_time = request.preferred_time
        existing_preference.preferred_venue = request.preferred_venue.strip()
        if existing_preference.preferred_venue not in ['Long Hall1', 'LongHall2', 'Science Education lab', 'FSLT1', 'FSLT2']:
                raise HTTPException(status_code=403, detail='Invalid venue selected')
        db.commit()
        db.refresh(existing_preference)
        return existing_preference
    
    new_preference = StudentSchedulePreference(
        student_id=loggedin.id,
        course_id=request.course_id,
        tutor_id=request.tutor_id,
        preferred_day=request.preferred_day,
        preferred_time=request.preferred_time,
        preferred_venue=request.preferred_venue.strip()
    )

    if new_preference.preferred_venue not in ['Long Hall1', 'Long Hall2', 'Science Education lab', 'FSLT1', 'FSLT 2']:
        raise HTTPException(status_code=403, detail='Invalid venue selected')
    
    db.add(new_preference)
    db.commit()
    db.refresh(new_preference)
    
    return new_preference

@router.get('/course/{course_id}/aggregate', response_model=CourseScheduleAggregation)
def get_course_schedule_aggregation(course_id: int, db: Session = Depends(get_db)):

    preferences = db.query(StudentSchedulePreference).filter(StudentSchedulePreference.course_id == course_id).all()
    
    if not preferences:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No schedule preferences found for this course"
        )
    
    tutor_counts = Counter([p.tutor_id for p in preferences])
    day_counts = Counter([p.preferred_day for p in preferences])
    time_counts = Counter([p.preferred_time for p in preferences])
    venue_counts = Counter([p.preferred_venue for p in preferences])
    
    return CourseScheduleAggregation(
        course_id=course_id,
        tutor_selections=dict(tutor_counts),
        day_selections=dict(day_counts),
        time_selections=dict(time_counts),
        venue_selections=dict(venue_counts),
        total_preferences=len(preferences)
    )

@router.post('/course/{course_id}/determine-schedule')
def determine_final_schedule(course_id: int, db: Session = Depends(get_db)):

    preferences = db.query(StudentSchedulePreference).filter(StudentSchedulePreference.course_id == course_id).all()
    
    if len(preferences) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient preferences. Got {len(preferences)} preferences, need at least 12. Invite friends to make a schedule for {course_id}"
        )
    
    tutor_counts = Counter([p.tutor_id for p in preferences])
    day_counts = Counter([p.preferred_day for p in preferences])
    time_counts = Counter([p.preferred_time for p in preferences])
    venue_counts = Counter([p.preferred_venue for p in preferences])
    
    most_popular_tutor_id = tutor_counts.most_common(1)[0][0]
    most_popular_day = day_counts.most_common(1)[0][0]
    most_popular_time = time_counts.most_common(1)[0][0]
    most_popular_venue = venue_counts.most_common(1)[0][0]
    
    tutor = db.query(Tutor).filter(Tutor.id == most_popular_tutor_id).first()
    
    existing_schedule = db.query(TutorialSchedule).filter(
        TutorialSchedule.course_id == course_id,
        TutorialSchedule.is_finalized == True
    ).first()
    
    if existing_schedule:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Schedule has been finalized for {course_id}")
    else:
        new_schedule = TutorialSchedule(
            course_id=course_id,
            tutor_id=most_popular_tutor_id,
            scheduled_day=most_popular_day,
            scheduled_time=most_popular_time,
            scheduled_venue=most_popular_venue,
            total_votes=len(preferences),
            is_finalized=True,
            finalized_at=datetime.utcnow()
        )
        db.add(new_schedule)
    
    db.commit()
    
    return {
        "message": "Schedule finalized successfully",
        "course_id": course_id,
        "final_schedule": {
            "tutor_id": most_popular_tutor_id,
            "tutor_name": tutor.username,
            "day": most_popular_day,
            "time": most_popular_time,
            "venue": most_popular_venue,
            "total_preferences": len(preferences)
        },
        "statistics": {
            "tutor_votes": dict(tutor_counts),
            "day_votes": dict(day_counts),
            "time_votes": dict(time_counts),
            "venue_votes": dict(venue_counts)
        }
    }

@router.get('/course/{course_id}/final-schedule', response_model=TutorialScheduleResponse)
def get_final_schedule(course_id: int, db: Session = Depends(get_db)):
    """
    Get the finalized schedule for a course
    """
    schedule = db.query(TutorialSchedule).filter(
        TutorialSchedule.course_id == course_id,
        TutorialSchedule.is_finalized == True
    ).first()
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No finalized schedule found for this course"
        )
    
    return schedule

@router.get('/student/my-preferences', response_model=List[SchedulePreferenceResponse])
def get_my_preferences(db: Session = Depends(get_db),loggedin: User = Depends(get_current_student)):

    preferences = db.query(StudentSchedulePreference).filter(StudentSchedulePreference.student_id == loggedin.id).all()
    return preferences

@router.delete('/preference/{course_id}')
def delete_my_preference(
    course_id: int,
    db: Session = Depends(get_db),
    loggedin: User = Depends(get_current_user)
):
    preference = db.query(StudentSchedulePreference).filter(
        StudentSchedulePreference.student_id == loggedin.id,
        StudentSchedulePreference.course_id == course_id
    ).first()
    
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preference not found"
        )
    
    db.delete(preference)
    db.commit()
    
    return {"message": "Preference deleted successfully"}

@router.get('/tutor/{tutor_id}/assigned-schedules', response_model=List[TutorialScheduleResponse])
def get_tutor_assigned_schedules(tutor_id: int, db: Session = Depends(get_db)):

    tutor = db.query(Tutor).filter(Tutor.id == tutor_id).first()
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found")
    
    schedules = db.query(TutorialSchedule).filter(TutorialSchedule.tutor_id == tutor_id, TutorialSchedule.is_finalized == True).all()
    
    return schedules

@router.get('/available-options/{course_id}')
def get_available_options(course_id: int, db: Session = Depends(get_db)):

    available_tutors = db.query(Tutor).all()
    available_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    available_times = ["9:00 AM", "11:00 AM", "12:00 PM", "4:00 PM", "5:00PM", "6:00PM", "7:00PM", "8:00PM"]
    available_venues = ["Long_Hall_1", "Long_Hall_2", "Faculty_of_Edu_Sci_Lab"]
    
    return {
        "course_id": course_id,
        "available_tutors": [
            {"id": t.id, "name": t.username, "specialty": t.specialty}
            for t in available_tutors
        ],
        "available_days": available_days,
        "available_times": available_times,
        "available_venues": available_venues
    }