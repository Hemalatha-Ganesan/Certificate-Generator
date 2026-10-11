from app.database import Base, engine, SessionLocal
from app.models import Job, Certificate
from app.service import process_job

Base.metadata.create_all(engine)

db = SessionLocal()
job = Job(course_title="Python Backend", date="11 October 2026", total=3)
job.certificates = [
    Certificate(name="Hemalatha", email="hema@example.com"),
    Certificate(name="Arun Kumar", email="arun@example.com"),
    Certificate(name="Priya", email="priya@example.com"),
]
db.add(job)
db.commit()
job_id = job.id
db.close()

process_job(job_id)

db = SessionLocal()
job = db.get(Job, job_id)
print(job.status, job.success_count, job.failed_count)
for c in job.certificates:
    print(c.name, c.status, c.file_path)
db.close()