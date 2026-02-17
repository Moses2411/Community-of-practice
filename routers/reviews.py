from fastapi import APIRouter, status, HTTPException, Depends
from model import Review, User, Tutor
from schemas import ReviewCreate, ReviewResponse
from auth.OAuth2 import get_current_student
from db.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix='/reviews', tags=['Reviews'])

@router.post('/create_review', response_model=ReviewResponse)
def create_review(request: ReviewCreate, db: Session = Depends(get_db), loggedin:User = Depends(get_current_student)):

    new_review = Review(
        tutor_id = request.tutor_id,
        student_id = loggedin.id,
        student_mail = loggedin.email,
        comment = request.comment,
        rating = request.rating
    )

    tutor = db.query(Tutor).filter(Tutor.id == request.tutor_id).first()
    if not tutor:
        raise HTTPException(status_code=404, detail=f"No tutor with id {request.tutor_id}")
    if new_review.rating not in ['excellent', 'good', 'poor']:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail= 'invlalid rating')
    
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    return new_review

@router.delete('/delete_review{review_id}')
def delete_review(review_id: int, db:Session = Depends(get_db), loggedin: User = Depends(get_current_student)):
    my_review = db.query(Review).filter(Review.student_id == loggedin.id).first()
    if not my_review:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='you are not authorized to delete this review because it does not belong to you')
    if my_review.id != review_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Review not found')
    db.delete(my_review)
    db.commit()
    return {f'You have sccessfully deleted your review with id {my_review.id}'}