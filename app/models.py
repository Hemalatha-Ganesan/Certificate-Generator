import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=new_id)
    course_title = Column(String, nullable=False)
    date = Column(String, nullable=False)
    # pending -> processing -> completed | completed_with_errors
    status = Column(String, nullable=False, default="pending")
    total = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    certificates = relationship(
        "Certificate", back_populates="job", cascade="all, delete-orphan"
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(String, primary_key=True, default=new_id)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    # pending | success | failed
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    file_path = Column(String, nullable=True)

    job = relationship("Job", back_populates="certificates")