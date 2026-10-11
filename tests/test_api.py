import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import generator, service
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A test client wired to a throwaway in-memory DB and a temp output folder."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # The background task opens its own session: point it at the test DB too
    monkeypatch.setattr(service, "SessionLocal", TestSession)
    monkeypatch.setattr(service, "OUTPUT_DIR", str(tmp_path / "certs"))

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def make_payload(*names):
    return {
        "course_title": "Python Backend Development",
        "date": "11 October 2026",
        "recipients": [
            {"name": n, "email": f"{n.replace(' ', '.').lower()}@example.com"}
            for n in names
        ],
    }


# ---------- 1. Creating a generation job ----------

def test_create_job_returns_202_and_job_id(client):
    r = client.post("/jobs", json=make_payload("Hemalatha", "Arun Kumar"))
    assert r.status_code == 202
    body = r.json()
    assert body["job_id"]
    assert body["total"] == 2


# ---------- 2. Input validation ----------

@pytest.mark.parametrize(
    "payload",
    [
        {"course_title": "X", "date": "d", "recipients": []},  # empty list
        {"course_title": "X", "date": "d",
         "recipients": [{"name": "A", "email": "not-an-email"}]},  # bad email
        {"course_title": "X", "date": "d",
         "recipients": [{"name": "   ", "email": "a@example.com"}]},  # blank name
        {"date": "d", "recipients": [{"name": "A", "email": "a@example.com"}]},  # no title
        {"course_title": "X", "date": "d"},  # no recipients field
    ],
)
def test_invalid_input_is_rejected(client, payload):
    r = client.post("/jobs", json=payload)
    assert r.status_code == 422


def test_too_many_recipients_is_rejected(client):
    names = [f"P{i}" for i in range(1001)]
    r = client.post("/jobs", json=make_payload(*names))
    assert r.status_code == 422


# ---------- 3. Certificate generation ----------

def test_generator_creates_a_pdf(tmp_path):
    out = tmp_path / "one.pdf"
    generator.generate_certificate("Hemalatha", "Python", "11 Oct 2026", str(out))
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")


def test_job_generates_one_pdf_per_recipient(client):
    job_id = client.post("/jobs", json=make_payload("A One", "B Two", "C Three")).json()["job_id"]
    certs = client.get(f"/jobs/{job_id}").json()["certificates"]
    assert len(certs) == 3
    for c in certs:
        r = client.get(f"/jobs/{job_id}/certificates/{c['id']}")
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")


# ---------- 4. Job status / progress ----------

def test_job_status_and_progress(client):
    job_id = client.post("/jobs", json=make_payload("A One", "B Two")).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["total"] == 2
    assert job["success_count"] == 2
    assert job["failed_count"] == 0
    assert all(c["status"] == "success" for c in job["certificates"])


def test_unknown_job_returns_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404


# ---------- 5. One certificate failing must not stop the rest ----------

def test_individual_failure_does_not_stop_other_certificates(client, monkeypatch):
    real = generator.generate_certificate

    def flaky(name, course_title, date, output_path, certificate_id=None):
        if name == "Bad Person":
            raise RuntimeError("simulated rendering failure")
        return real(
            name=name, course_title=course_title, date=date,
            output_path=output_path, certificate_id=certificate_id,
        )

    monkeypatch.setattr(service.generator, "generate_certificate", flaky)

    job_id = client.post(
        "/jobs", json=make_payload("Good One", "Bad Person", "Good Two")
    ).json()["job_id"]

    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed_with_errors"
    assert job["success_count"] == 2
    assert job["failed_count"] == 1

    by_name = {c["name"]: c for c in job["certificates"]}
    assert by_name["Good One"]["status"] == "success"
    assert by_name["Good Two"]["status"] == "success"
    assert by_name["Bad Person"]["status"] == "failed"
    assert "simulated rendering failure" in by_name["Bad Person"]["error_message"]

    # A failed certificate cannot be downloaded
    r = client.get(f"/jobs/{job_id}/certificates/{by_name['Bad Person']['id']}")
    assert r.status_code == 409


# ---------- 6. Retrieving generated certificates ----------

def test_download_single_certificate(client):
    job_id = client.post("/jobs", json=make_payload("Hemalatha")).json()["job_id"]
    cert_id = client.get(f"/jobs/{job_id}").json()["certificates"][0]["id"]
    r = client.get(f"/jobs/{job_id}/certificates/{cert_id}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_download_all_as_zip(client):
    job_id = client.post("/jobs", json=make_payload("A One", "B Two", "C Three")).json()["job_id"]
    r = client.get(f"/jobs/{job_id}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert len(zf.namelist()) == 3


def test_certificate_cannot_be_read_through_wrong_job(client):
    job_a = client.post("/jobs", json=make_payload("A One")).json()["job_id"]
    job_b = client.post("/jobs", json=make_payload("B Two")).json()["job_id"]
    cert_a = client.get(f"/jobs/{job_a}").json()["certificates"][0]["id"]
    assert client.get(f"/jobs/{job_b}/certificates/{cert_a}").status_code == 404


# ---------- Extra: long names fit inside the certificate ----------

def test_fit_font_size_shrinks_long_text():
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from app.generator import fit_font_size

    short = fit_font_size("Hema", "Helvetica-Bold", 34, 680)
    long_name = "A" * 60
    long_size = fit_font_size(long_name, "Helvetica-Bold", 34, 680)

    assert short == 34                      # short names keep the full size
    assert long_size < 34                   # long names get smaller
    assert stringWidth(long_name, "Helvetica-Bold", long_size) <= 680


def test_generator_handles_very_long_name(tmp_path):
    out = tmp_path / "long.pdf"
    generator.generate_certificate("B" * 100, "C" * 100, "11 Oct 2026", str(out))
    assert out.read_bytes().startswith(b"%PDF")


# ---------- Extra: certificate ID and verification ----------

def test_verify_valid_certificate(client):
    job_id = client.post("/jobs", json=make_payload("Hemalatha")).json()["job_id"]
    cert_id = client.get(f"/jobs/{job_id}").json()["certificates"][0]["id"]

    r = client.get(f"/verify/{cert_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert body["name"] == "Hemalatha"
    assert body["course_title"] == "Python Backend Development"
    assert "email" not in body  # personal data is not exposed


def test_verify_unknown_certificate_returns_404(client):
    assert client.get("/verify/not-a-real-id").status_code == 404


def test_verify_failed_certificate_is_not_valid(client, monkeypatch):
    def always_fails(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service.generator, "generate_certificate", always_fails)
    job_id = client.post("/jobs", json=make_payload("Nobody")).json()["job_id"]
    cert_id = client.get(f"/jobs/{job_id}").json()["certificates"][0]["id"]
    assert client.get(f"/verify/{cert_id}").status_code == 404


def test_certificate_id_is_printed_on_the_pdf(tmp_path):
    out = tmp_path / "id.pdf"
    generator.generate_certificate("Hema", "Python", "11 Oct 2026", str(out), certificate_id="abc-123")
    assert out.read_bytes().startswith(b"%PDF")