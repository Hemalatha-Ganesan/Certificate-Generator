import os

from app import generator
from app.database import SessionLocal
from app.models import Job, Certificate

OUTPUT_DIR = "certificates"
# Address printed in each certificate's QR code. Set PUBLIC_BASE_URL when deployed.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")


def process_job(job_id: str, session_factory=None) -> None:
    """Generate a certificate for every recipient in the job.

    Each recipient is handled in its own try/except, so one failure
    never stops the others.
    """
    # Looked up at call time (not import time) so tests can swap SessionLocal
    db = (session_factory or SessionLocal)()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return

        job.status = "processing"
        db.commit()

        job_dir = os.path.join(OUTPUT_DIR, job.id)
        os.makedirs(job_dir, exist_ok=True)

        for cert in job.certificates:
            try:
                path = os.path.join(job_dir, f"{cert.id}.pdf")
                generator.generate_certificate(
                    name=cert.name,
                    course_title=job.course_title,
                    date=job.date,
                    output_path=path,
                    certificate_id=cert.id,
                    verify_url=f"{PUBLIC_BASE_URL.rstrip('/')}/verify/{cert.id}",
                )
                cert.status = "success"
                cert.file_path = path
                job.success_count += 1
            except Exception as exc:
                cert.status = "failed"
                cert.error_message = str(exc)[:500]
                job.failed_count += 1
            db.commit()

        job.status = (
            "completed_with_errors" if job.failed_count > 0 else "completed"
        )
        db.commit()
    finally:
        db.close()