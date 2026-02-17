from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from model import Poll, User, Tutor, Course
from schemas import PollResponse, CreatePoll
from db.database import get_db
from auth.OAuth2 import get_current_user

router = APIRouter(prefix='/poll', tags=['Poll'])

@router.post('/create_poll', response_model=PollResponse)
def create_poll(request: CreatePoll, db:Session = Depends(get_db), loggedin: User = Depends(get_current_user)):

    tutor = db.query(Tutor).filter(Tutor.id == request.tutor_id).first()
    course = db.query(Course).filter(Course.id == request.course_id).first()
    if not tutor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tutor not found")
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='course not found')
    
    create_poll = Poll(
         course_id = request.course_id,
         tutor_id = request.tutor_id,
         day = request.day,
         time = request.time,
         venue = request.venue
    )

    db.add(create_poll)
    db.commit()
    db.refresh(create_poll)
    return create_poll

# Add these endpoints to poll.py

@router.get('/course/{course_id}/polls')
def get_polls_for_course(course_id: int, db: Session = Depends(get_db)):
    """
    Get all polls for a specific course
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    polls = db.query(Poll).filter(Poll.course_id == course_id).all()
    
    return {
        "course_id": course_id,
        "course_title": course.title,
        "total_polls": len(polls),
        "polls": [
            {
                "id": poll.id,
                "tutor_id": poll.tutor_id,
                "day": poll.day,
                "time": poll.time,
                "venue": poll.venue,
                "votes": poll.votes
            }
            for poll in polls
        ]
    }

@router.get('/tutor/{tutor_id}/polls')
def get_polls_by_tutor(tutor_id: int, db: Session = Depends(get_db)):
    """
    Get all polls created by a specific tutor
    """
    tutor = db.query(Tutor).filter(Tutor.id == tutor_id).first()
    if not tutor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tutor not found"
        )
    
    polls = db.query(Poll).filter(Poll.tutor_id == tutor_id).all()
    
    return {
        "tutor_id": tutor_id,
        "tutor_name": tutor.username,
        "total_polls": len(polls),
        "polls": [
            {
                "id": poll.id,
                "course_id": poll.course_id,
                "day": poll.day,
                "time": poll.time,
                "venue": poll.venue,
                "votes": poll.votes
            }
            for poll in polls
        ]
    }