import os
import tempfile
import subprocess
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="HTML to PDF (wkhtmltopdf)")

# Optional: enable CORS if you call from browser / other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/html_to_pdf")
async def html_to_pdf(request: Request):
    """
    Accepts raw HTML in the request body (Content-Type: text/html).
    Assumes HTML already contains embedded base64 images / inline SVG OR
    references local files using file:// URLs (requires --enable-local-file-access).
    Converts using wkhtmltopdf and returns PDF.
    """
    # read raw bytes then decode (preserve exact bytes)
    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(status_code=400, detail="Request body must contain raw HTML.")

    try:
        html_content = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # fallback: try latin-1 (unlikely)
        html_content = body_bytes.decode("latin-1")

    # create temporary folder and files
    with tempfile.TemporaryDirectory() as td:
        html_path = os.path.join(td, "bill2.html")
        pdf_path = os.path.join("output.pdf")

        # write HTML to temp file
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # build wkhtmltopdf command
        # (Use absolute path to wkhtmltopdf exe if it's not on PATH)
        cmd = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            "--enable-local-file-access",
            "--image-quality", "100",
            "--dpi", "150",
            # Add these lines to control or remove margins:
            "--margin-top", "10mm",
            "--margin-bottom", "10mm",
            "--margin-left", "10mm",
            "--margin-right", "10mm",
            # "--quiet",  # you can uncomment to suppress stdout; keep commented for easier debugging
            html_path,
            pdf_path,
        ]

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
            )
        except FileNotFoundError:
            # wkhtmltopdf not found on PATH
            raise HTTPException(
                status_code=500,
                detail="wkhtmltopdf not found. Install wkhtmltopdf or set the full path in the command."
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=500, detail="wkhtmltopdf timed out.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Conversion error: {e}")

        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="ignore")
            # include a short snippet for debugging
            raise HTTPException(status_code=500, detail=f"wkhtmltopdf failed: {stderr[:2000]}")

        # return the PDF file
        return FileResponse(path=pdf_path, media_type="application/pdf", filename="document.pdf")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8085,
        reload=True,
        log_level="debug"
    )
