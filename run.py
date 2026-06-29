import os

PORT = int(os.environ.get("PORT", "8000"))
WORKERS = int(os.environ.get("WEB_CONCURRENCY", "1"))

if __name__ == "__main__":
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import inspect
    from pathlib import Path

    from sqlalchemy import text

    from app.practical_schedule import ensure_practical_release_schema
    from app.seed import seed_database
    from db.database import Base, SessionLocal, engine

    alembic_cfg = Config(Path(__file__).resolve().parent / "alembic.ini")
    inspector = inspect(engine)

    Base.metadata.create_all(bind=engine)

    if "alembic_version" not in inspector.get_table_names():
        command.stamp(alembic_cfg, "head")
    else:
        command.upgrade(alembic_cfg, "head")

    with engine.connect() as conn:
        for col in ["attachment_url", "attachment_name", "attachment_type"]:
            try:
                conn.execute(text(f"ALTER TABLE chat_messages ADD COLUMN {col} VARCHAR"))
                conn.commit()
            except Exception:
                conn.rollback()
        for col in ["file_url", "file_name"]:
            try:
                conn.execute(text(f"ALTER TABLE resources ADD COLUMN {col} VARCHAR"))
                conn.commit()
            except Exception:
                conn.rollback()


    Path("uploads").mkdir(parents=True, exist_ok=True)

    ensure_practical_release_schema()
    with SessionLocal() as db:
        seed_database(db)

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        workers=WORKERS,
    )
