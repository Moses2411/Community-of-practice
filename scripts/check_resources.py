"""Check all resource URLs for availability."""
import os, sys, httpx
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sqlalchemy import select
from db.database import SessionLocal
from model import Resource, Course

def check_url(url, label):
    try:
        r = httpx.head(url, follow_redirects=True, timeout=10)
        if r.status_code < 400:
            return f"  OK ({r.status_code})"
        return f"  BROKEN ({r.status_code})"
    except Exception as e:
        return f"  ERROR ({e})"

with SessionLocal() as db:
    resources = db.scalars(
        select(Resource).order_by(Resource.created_at.desc())
    ).all()

    if not resources:
        print("No resources found in database.")
        exit(0)

    print(f"Found {len(resources)} resources:\n")
    for r in resources:
        course = db.get(Course, r.course_id)
        course_label = f"{course.code}: {course.title}" if course else "?"
        print(f"[{r.id}] {r.title} ({course_label})")
        if r.url:
            print(f"  url:        {check_url(r.url, 'url')}")
        if r.video_url:
            print(f"  video_url:  {check_url(r.video_url, 'video')}")
        if r.blog_url:
            print(f"  blog_url:   {check_url(r.blog_url, 'blog')}")
        if not r.url and not r.video_url and not r.blog_url:
            print(f"  (body-only resource, no URLs to check)")
        print()
