"""Parse untrusted office documents in a subprocess with a bounded lifetime."""
from __future__ import annotations

import subprocess
import sys

from .loaders import extract_text_from_docx, extract_text_from_pdf, sanitize

MAX_TEXT = 60_000
_MAX_PDF_PAGES = 60
_MAX_DOCX_XML = 2 * 1024 * 1024


def extract_upload(extension: str, data: bytes) -> str:
    if not data:
        raise ValueError("The file is empty.")
    if extension in (".md", ".txt"):
        try:
            return _checked_text(data.decode("utf-8-sig"))
        except UnicodeDecodeError:
            raise ValueError("Text and Markdown files must be UTF-8.") from None
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("The file does not have a PDF header.")
    if extension == ".docx" and not data.startswith(b"PK\x03\x04"):
        raise ValueError("The file does not have a DOCX header.")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.web_extract", extension],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=True,
            env={"PYTHONIOENCODING": "utf-8"},
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        raise ValueError("Could not read this document within the file, page, or extraction limits.") from None
    return result.stdout.decode("utf-8")


def _checked_text(text: str) -> str:
    if len(text) > MAX_TEXT:
        raise ValueError(f"A document may contain at most {MAX_TEXT:,} extracted characters.")
    text = sanitize(text).strip()
    if not text:
        raise ValueError("No readable text found in this file.")
    return text


if __name__ == "__main__":
    try:
        import resource
    except ImportError:
        pass  # Local Windows development still has the wall-clock timeout.
    else:
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024**2, 128 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (6, 7))

    payload = sys.stdin.buffer.read()
    extension = sys.argv[1]
    if extension == ".pdf":
        text = extract_text_from_pdf(payload, max_pages=_MAX_PDF_PAGES)
    else:
        text = extract_text_from_docx(payload, max_xml=_MAX_DOCX_XML)
    sys.stdout.write(_checked_text(text))
