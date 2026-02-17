from enum import Enum
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from db.database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    program = Column(String, nullable=True)
    
    votes = relationship("Vote", back_populates="student", cascade="all, delete-orphan")
    reviews_given = relationship("Review", back_populates="student", foreign_keys="Review.student_id")


class Tutor(Base):
    __tablename__ = "tutors"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    specialty = Column(String)
    department = Column(String)
    
    polls = relationship("Poll", back_populates="tutor", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="tutor", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    title = Column(String, unique=False)
    course_code = Column(String, nullable=True)
    
    polls = relationship("Poll", back_populates="course", cascade="all, delete-orphan")


class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    tutor_id = Column(Integer, ForeignKey("tutors.id", ondelete="CASCADE"))
    day = Column(String)
    time = Column(String)
    venue = Column(String)
    votes = Column(Integer, default=0)
    
    course = relationship("Course", back_populates="polls")
    tutor = relationship("Tutor", back_populates="polls")
    votes_list = relationship("Vote", back_populates="poll", cascade="all, delete-orphan")


class Vote(Base):
    __tablename__ = "votes"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id", ondelete="CASCADE"))
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    
    # Relationships
    poll = relationship("Poll", back_populates="votes_list")
    student = relationship("User", back_populates="votes")


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    tutor_id = Column(Integer, ForeignKey("tutors.id", ondelete="CASCADE"))
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    rating = Column(String, nullable = False)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tutor = relationship("Tutor", back_populates="reviews")
    student = relationship("User", back_populates="reviews_given", foreign_keys=[student_id])


class StudentSchedulePreference(Base):
    __tablename__ = "student_schedule_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    tutor_id = Column(Integer, ForeignKey("tutors.id", ondelete="CASCADE"))
    preferred_day = Column(String)
    preferred_time = Column(String)
    preferred_venue = Column(String)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship("User", backref="schedule_preferences")
    course = relationship("Course", backref="preferences")
    tutor = relationship("Tutor", backref="preferred_schedules")
    
    # Ensure each student can only submit one preference per course
    __table_args__ = (
        UniqueConstraint('student_id', 'course_id', name='unique_student_course_preference'),
    )

class TutorialSchedule(Base):
    __tablename__ = "tutorial_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))
    tutor_id = Column(Integer, ForeignKey("tutors.id", ondelete="CASCADE"))
    scheduled_day = Column(String)
    scheduled_time = Column(String)
    scheduled_venue = Column(String)
    total_votes = Column(Integer, default=0)
    is_finalized = Column(Boolean, default=False)
    finalized_at = Column(DateTime, nullable=True)
    
    # Relationships
    course = relationship("Course", backref="final_schedule")
    tutor = relationship("Tutor", backref="assigned_schedules")


class Ratings(str, Enum):
    Excellent = 'excellent'
    Good = 'good'
    Poor = 'poor'


class Venue(str, Enum):
    long_hall_1 = 'Long_Hall_1'
    long_hall_2 = 'Long_Hall_2'
    faculty_of_edu_sci_lab = 'Faculty_of_Edu_Sci_Lab'