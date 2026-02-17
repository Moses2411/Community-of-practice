from fastapi import FastAPI
from db.database import engine
import model
from routers import auth, courses, reviews, poll, schedule, votes, tutor, student

app = FastAPI(
    title="Community_of_Practice",
    version="1.0"
)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(schedule.router)
app.include_router(student.router)
app.include_router(tutor.router)
app.include_router(reviews.router)

@app.get('/')
def root():
    return {'message': "welcome to COP"}

model.Base.metadata.create_all(engine)