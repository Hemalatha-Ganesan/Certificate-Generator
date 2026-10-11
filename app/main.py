import io
import os
import zipfile

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app import models, schemas, service
from app.database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bulk Certificate Generator API")


@app.post("/jobs", response_model=schemas.JobCreated, status_code=202)
def create_job(
    payload: schemas.JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job = models.Job(
        course_title=payload.course_title,
        date=payload.date,
        total=len(payload.recipients),
    )
    job.certificates = [
        models.Certificate(name=r.name, email=r.email)
        for r in payload.recipients
    ]
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(service.process_job, job.id)
    return schemas.JobCreated(job_id=job.id, status=job.status, total=job.total)


@app.get("/jobs/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs/{job_id}/certificates/{certificate_id}")
def download_certificate(
    job_id: str, certificate_id: str, db: Session = Depends(get_db)
):
    cert = db.get(models.Certificate, certificate_id)
    if cert is None or cert.job_id != job_id:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert.status != "success" or not cert.file_path or not os.path.exists(cert.file_path):
        raise HTTPException(status_code=409, detail="Certificate is not available")
    return FileResponse(
        cert.file_path,
        media_type="application/pdf",
        filename=f"{cert.name}.pdf",
    )


@app.get("/jobs/{job_id}/download")
def download_all(job_id: str, db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    ready = [
        c for c in job.certificates
        if c.status == "success" and c.file_path and os.path.exists(c.file_path)
    ]
    if not ready:
        raise HTTPException(status_code=409, detail="No certificates available yet")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, c in enumerate(ready, start=1):
            safe_name = "".join(ch for ch in c.name if ch.isalnum() or ch in " -_").strip()
            zf.write(c.file_path, arcname=f"{i:03d}_{safe_name}.pdf")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="job_{job_id}.zip"'},
    )


@app.get("/verify/{certificate_id}", response_model=schemas.VerifyOut)
def verify_certificate(certificate_id: str, db: Session = Depends(get_db)):
    cert = db.get(models.Certificate, certificate_id)
    if cert is None or cert.status != "success":
        raise HTTPException(status_code=404, detail="Certificate not found or not valid")
    return schemas.VerifyOut(
        valid=True,
        certificate_id=cert.id,
        name=cert.name,
        course_title=cert.job.course_title,
        date=cert.job.date,
    )

@app.get("/", include_in_schema=False)
def root():
    return {"message": "Bulk Certificate Generator API", "docs": "/docs"}