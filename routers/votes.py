from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from model import Vote, Poll, User, Tutor, Course
from schemas import VoteCreate, VoteResponse, PollResponse
from db.database import get_db
from auth.OAuth2 import get_current_user
from typing import List

router = APIRouter(prefix='/votes', tags=['Votes'])

@router.post('/vote', response_model=VoteResponse)
def vote_for_poll(request: VoteCreate, db: Session = Depends(get_db), loggedin: User = Depends(get_current_user)):
    """
    Vote for a specific poll
    """
    # Check if poll exists
    poll = db.query(Poll).filter(Poll.id == request.poll_id).first()
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll not found"
        )
    
    # Check if student has already voted for this poll
    existing_vote = db.query(Vote).filter(
        Vote.poll_id == request.poll_id,
        Vote.student_id == loggedin.id
    ).first()
    
    if existing_vote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already voted for this poll"
        )
    
    # Create new vote
    new_vote = Vote(
        poll_id=request.poll_id,
        student_id=loggedin.id
    )
    
    # Update poll vote count
    poll.votes = poll.votes + 1
    
    db.add(new_vote)
    db.commit()
    db.refresh(new_vote)
    
    return new_vote

@router.delete('/remove_vote/{poll_id}')
def remove_vote(poll_id: int, db: Session = Depends(get_db), loggedin: User = Depends(get_current_user)):
    """
    Remove vote from a poll
    """
    vote = db.query(Vote).filter(
        Vote.poll_id == poll_id,
        Vote.student_id == loggedin.id
    ).first()
    
    if not vote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vote not found"
        )
    
    # Update poll vote count
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if poll and poll.votes > 0:
        poll.votes = poll.votes - 1
    
    db.delete(vote)
    db.commit()
    
    return {"message": "Vote removed successfully"}

@router.get('/poll/{poll_id}/results')
def get_poll_results(poll_id: int, db: Session = Depends(get_db)):
    """
    Get results for a specific poll
    """
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poll not found"
        )
    
    # Get total votes for this poll
    total_votes = poll.votes
    
    return {
        "poll_id": poll.id,
        "course_id": poll.course_id,
        "tutor_id": poll.tutor_id,
        "day": poll.day,
        "time": poll.time,
        "venue": poll.venue,
        "total_votes": total_votes
    }

@router.get('/course/{course_id}/winning-poll')
def get_winning_poll_for_course(course_id: int, db: Session = Depends(get_db)):
    """
    Get the winning poll for a course (must have at least 12 votes)
    """
    # Get all polls for this course
    course_polls = db.query(Poll).filter(Poll.course_id == course_id).all()
    
    if not course_polls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No polls found for this course"
        )
    
    # Find the poll with maximum votes
    winning_poll = max(course_polls, key=lambda x: x.votes)
    
    # Check if winning poll has at least 12 votes
    if winning_poll.votes < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient votes. Winning poll has only {winning_poll.votes} votes. Need at least 12 votes to decide schedule."
        )
    
    # Get tutor and course details
    tutor = db.query(Tutor).filter(Tutor.id == winning_poll.tutor_id).first()
    course = db.query(Course).filter(Course.id == winning_poll.course_id).first()
    
    return {
        "winning_poll": {
            "poll_id": winning_poll.id,
            "day": winning_poll.day,
            "time": winning_poll.time,
            "venue": winning_poll.venue,
            "votes": winning_poll.votes
        },
        "tutor": {
            "id": tutor.id,
            "name": tutor.username,
            "specialty": tutor.specialty
        },
        "course": {
            "id": course.id,
            "title": course.title,
            "course_code": course.course_code
        },
        "final_schedule": {
            "course": course.title,
            "tutor": tutor.username,
            "day": winning_poll.day,
            "time": winning_poll.time,
            "venue": winning_poll.venue,
            "total_votes": winning_poll.votes
        }
    }