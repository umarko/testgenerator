from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from app.services.html_text import html_to_text


TEXT_EXTENSIONS = {
    ".csv",
    ".html",
    ".htm",
    ".json",
    ".log",
    ".md",
    ".sql",
    ".text",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def extract_attachment_text(file_name: str, content: bytes) -> tuple[str, str]:
    suffix = Path(file_name).suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        return _decode_text(content), "text-extracted"

    if suffix == ".docx":
        text = _extract_docx_text(content)
        return text, "text-extracted" if text else "empty-or-unsupported"

    if suffix == ".pdf":
        text = _extract_pdf_text(content)
        return text, "text-extracted" if text else "empty-or-unsupported"

    return "", "unsupported-file-type"


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1250", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _extract_docx_text(content: bytes) -> str:
    with ZipFile(BytesIO(content)) as docx:
        document_xml = docx.read("word/document.xml")

    root = ET.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        line = " ".join(part.strip() for part in texts if part and part.strip())
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def _extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    reader = PdfReader(BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(page.strip() for page in pages if page.strip())


def normalize_html_attachment(content: bytes) -> str:
    return html_to_text(_decode_text(content))

