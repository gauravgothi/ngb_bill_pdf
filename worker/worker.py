# worker/worker.py
import os
import json
import tempfile
import subprocess
from datetime import datetime

import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
QUEUE_NAME = os.getenv("PDF_QUEUE_NAME", "queue:pdf_jobs")
PDF_OUTPUT_DIR = os.getenv("PDF_OUTPUT_DIR", "/data/pdfs")
WKHTML_BIN = os.getenv("WKHTML_BIN", "/usr/bin/wkhtmltopdf")

os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def update_job(job_id: str, **fields):
    job_key = f"job:{job_id}"
    fields["updated_at"] = datetime.utcnow().isoformat()
    r.hset(job_key, mapping=fields)

def run_wkhtml(job_id: str, html: str) -> str:
    """
    Run wkhtmltopdf on given HTML string and store as {job_id}.pdf in PDF_OUTPUT_DIR.
    Returns final pdf path.
    """
    with tempfile.TemporaryDirectory() as td:
        html_path = os.path.join(td, "input.html")
        pdf_tmp = os.path.join(td, "output.pdf")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        cmd = [
            WKHTML_BIN,
            "--enable-local-file-access",
            "--image-quality", "100",
            "--dpi", "150",
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
            raise RuntimeError("wkhtmltopdf completed but output.pdf not found")

        final_path = os.path.join(PDF_OUTPUT_DIR, f"{job_id}.pdf")
        os.replace(pdf_tmp, final_path)
        return final_path

def worker_loop():
    print("Worker started, waiting for jobs...")
    while True:
        # BLPOP blocks until a job arrives
        item = r.blpop(QUEUE_NAME, timeout=5)
        if item is None:
            continue  # timeout -> loop again

        _, raw = item
        try:
            job = json.loads(raw)
        except Exception as e:
            print("Invalid job payload, skipping:", e)
            continue

        job_id = job.get("job_id")
        html = job.get("html")

        if not job_id or html is None:
            print("Job missing job_id or html; skipping.")
            continue

        print(f"Processing job {job_id}")
        update_job(job_id, status="RUNNING", error="")

        try:
            pdf_path = run_wkhtml(job_id, html)
            print(f"Job {job_id} completed: {pdf_path}")
            update_job(job_id, status="DONE", error="", pdf_path=pdf_path)
        except Exception as e:
            print(f"Job {job_id} failed:", e)
            update_job(job_id, status="FAILED", error=str(e))

if __name__ == "__main__":
    worker_loop()
