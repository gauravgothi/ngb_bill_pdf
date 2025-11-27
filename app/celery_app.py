# app/celery_app.py
import os
import tempfile
import subprocess

from celery import Celery

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
PDF_OUTPUT_DIR = os.getenv("PDF_OUTPUT_DIR", "/data/pdfs")
WKHTML_BIN = os.getenv("WKHTML_BIN", "/usr/bin/wkhtmltopdf")

os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

celery = Celery(
    "pdf_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)


@celery.task(name="generate_pdf")
def generate_pdf(html: str, job_id: str) -> dict:
    """
    Celery task: HTML -> PDF using wkhtmltopdf.
    Saves PDF as /data/pdfs/{job_id}.pdf (inside container).
    Returns {"pdf_path": "..."} for the API to read.
    """
    import os

    with tempfile.TemporaryDirectory() as td:
        html_path = os.path.join(td, "input.html")
        pdf_tmp = os.path.join(td, "output.pdf")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        cmd = [
            WKHTML_BIN,
            "--enable-local-file-access",
            "--image-quality",
            "100",
            "--dpi",
            "150",
            "--margin-top", "10mm",
            "--margin-bottom", "10mm",
            "--margin-left", "10mm",
            "--margin-right", "10mm",
            html_path,
            pdf_tmp,
        ]

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
        )

        stdout = proc.stdout.decode("utf-8", errors="ignore")
        stderr = proc.stderr.decode("utf-8", errors="ignore")
        if proc.returncode != 0:
            raise RuntimeError(f"wkhtmltopdf rc={proc.returncode} stderr={stderr[:1000]}")

        if not os.path.exists(pdf_tmp):
            raise RuntimeError("wkhtmltopdf finished but output.pdf not found")

        final_path = os.path.join(PDF_OUTPUT_DIR, f"{job_id}.pdf")
        os.replace(pdf_tmp, final_path)

        return {"pdf_path": final_path, "stdout": stdout[:500], "stderr": stderr[:500]}
