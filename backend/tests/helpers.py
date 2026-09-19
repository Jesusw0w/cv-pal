import zipfile
from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfWriter

DEFAULT_TEST_EMAIL = "test@example.com"
DEFAULT_TEST_PASSWORD = "orbital-lemur-7-quilt"  # noqa: S105  # test fixture credential


def _build_minimal_pdf() -> bytes:
    """Build a real single-page PDF.

    Written with pypdf rather than hand-rolled, so it carries a valid xref table and
    survives both magic-byte validation and parsing.

    Returns:
        The PDF file bytes.
    """
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


MINIMAL_PDF = _build_minimal_pdf()


def linkedin_archive(files: dict[str, str]) -> bytes:
    """Build a LinkedIn-shaped export archive from member name to CSV body."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


async def register_and_login(
    client: AsyncClient,
    *,
    email: str = DEFAULT_TEST_EMAIL,
    password: str = DEFAULT_TEST_PASSWORD,
) -> dict[str, str]:
    """Register a user and return an Authorization header for them.

    Args:
        client: The test HTTP client.
        email: Email to register.
        password: Password to register.

    Returns:
        An Authorization header carrying the user's bearer token.
    """
    await client.post("/auth/register", json={"email": email, "password": password})
    response = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def upload_cv(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    filename: str = "cv.pdf",
    content: bytes = MINIMAL_PDF,
) -> int:
    """Upload a CV and return its ID.

    Args:
        client: The test HTTP client.
        headers: Authorization headers.
        filename: Name to upload the file under.
        content: File bytes.

    Returns:
        The created CV's ID.
    """
    response = await client.post(
        "/cvs/",
        headers=headers,
        files={"file": (filename, BytesIO(content), "application/pdf")},
    )
    cv_id: int = response.json()["id"]
    return cv_id
