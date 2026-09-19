from pathlib import Path

import anyio.to_thread
from docx import Document
from pypdf import PdfReader

from cv_pal.exceptions import UnsupportedFileTypeError


def _extract_text_from_pdf(file_path: Path) -> str:
    """Extract text content from a PDF file.

    Args:
        file_path: Path to the PDF file.

    Returns:
        The extracted text, one block per page.
    """
    reader = PdfReader(file_path)
    parts = [page.extract_text() for page in reader.pages]
    return "\n".join(part for part in parts if part)


def _extract_text_from_docx(file_path: Path) -> str:
    """Extract text content from a DOCX file.

    Args:
        file_path: Path to the DOCX file.

    Returns:
        The extracted text, one block per paragraph.
    """
    document = Document(str(file_path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extract_text_sync(file_path: Path) -> str:
    """Extract text from a CV file based on its extension.

    Args:
        file_path: Path to the CV file.

    Returns:
        The extracted text content.

    Raises:
        UnsupportedFileTypeError: If the file type is not supported.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_text_from_pdf(file_path)
    if suffix == ".docx":
        return _extract_text_from_docx(file_path)
    raise UnsupportedFileTypeError(suffix)


async def extract_cv_text(file_path: Path) -> str:
    """Extract text from a CV file without blocking the event loop.

    Parsing a large PDF is CPU-bound and can take seconds, so it runs in a worker
    thread rather than on the event loop.

    Args:
        file_path: Path to the CV file.

    Returns:
        The extracted text content.

    Raises:
        UnsupportedFileTypeError: If the file type is not supported.
    """
    return await anyio.to_thread.run_sync(extract_text_sync, file_path)
