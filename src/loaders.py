"""Read text from notes in .md, .txt, .pdf and .docx form (no extra dependencies for .docx)."""
from __future__ import annotations

import io
import os
import zipfile
import xml.etree.ElementTree as ET

SUPPORTED = (".md", ".txt", ".pdf", ".docx")

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MAX_DOCX_XML = 50 * 1024 * 1024  # refuse zip bombs


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from PDF bytes. Requires pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PDF support needs 'pypdf'. Install it with: pip install pypdf") from exc
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract paragraph and table text from a .docx (an OOXML zip), standard library only.

    Headings become Markdown headings so the chunker can split on them.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            info = z.getinfo("word/document.xml")
            if info.file_size > _MAX_DOCX_XML:
                raise ValueError("document.xml is too large")
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ValueError("Not a valid .docx file") from exc

    lines: list[str] = []
    for p in root.iter(f"{_W}p"):
        parts = []
        for node in p.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append("\t")
        text = "".join(parts).strip()
        if not text:
            lines.append("")
            continue
        style = p.find(f"{_W}pPr/{_W}pStyle")
        style_id = style.get(f"{_W}val", "") if style is not None else ""
        if style_id.lower().startswith("heading") and style_id[7:].isdigit():
            text = "#" * min(int(style_id[7:]), 6) + " " + text
        elif p.find(f"{_W}pPr/{_W}numPr") is not None:
            text = "- " + text
        lines.append(text)
    out = "\n".join(lines)
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out.strip()


def extract_text(name: str, data: bytes) -> str:
    """Return the text of a file given its name (for the extension) and its bytes."""
    ext = os.path.splitext(name)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(data)
    if ext == ".docx":
        return extract_text_from_docx(data)
    if ext in (".md", ".txt"):
        return data.decode("utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {ext or name!r} (supported: {', '.join(SUPPORTED)})")


def read_file(path: str) -> str:
    with open(path, "rb") as f:
        return extract_text(os.path.basename(path), f.read())
