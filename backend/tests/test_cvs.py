from io import BytesIO
from pathlib import Path

from httpx import AsyncClient

from cv_pal.constants import (
    DEFAULT_ERROR_CV_NOT_FOUND,
    DEFAULT_ERROR_FILE_CONTENT_MISMATCH,
)
from tests.helpers import MINIMAL_PDF, register_and_login, upload_cv


async def test_upload_cv(client: AsyncClient, upload_dir: Path) -> None:
    """A valid PDF is stored and recorded."""
    headers = await register_and_login(client)

    response = await client.post(
        "/cvs/",
        headers=headers,
        files={"file": ("cv.pdf", BytesIO(MINIMAL_PDF), "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "cv.pdf"
    assert len(list(upload_dir.iterdir())) == 1


async def test_upload_cv_generates_storage_key(
    client: AsyncClient, upload_dir: Path
) -> None:
    """The stored filename is generated, never taken from the client."""
    headers = await register_and_login(client)

    await client.post(
        "/cvs/",
        headers=headers,
        files={"file": ("../../escape.pdf", BytesIO(MINIMAL_PDF), "application/pdf")},
    )

    stored = list(upload_dir.iterdir())
    assert len(stored) == 1
    assert stored[0].name != "escape.pdf"
    assert stored[0].parent == upload_dir


async def test_upload_cv_invalid_type(client: AsyncClient) -> None:
    """An unsupported extension is rejected."""
    headers = await register_and_login(client)

    response = await client.post(
        "/cvs/",
        headers=headers,
        files={"file": ("notes.txt", BytesIO(b"content"), "text/plain")},
    )

    assert response.status_code == 400


async def test_upload_cv_content_type_mismatch(
    client: AsyncClient, upload_dir: Path
) -> None:
    """A file whose bytes do not match its extension is rejected and not stored."""
    headers = await register_and_login(client)

    response = await client.post(
        "/cvs/",
        headers=headers,
        files={"file": ("fake.pdf", BytesIO(b"not really a pdf"), "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == DEFAULT_ERROR_FILE_CONTENT_MISMATCH
    assert list(upload_dir.iterdir()) == []


async def test_list_cvs(client: AsyncClient) -> None:
    """A user's CVs are listed."""
    headers = await register_and_login(client)
    await upload_cv(client, headers, filename="cv1.pdf")
    await upload_cv(client, headers, filename="cv2.pdf")

    response = await client.get("/cvs/", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_list_cvs_respects_limit(client: AsyncClient) -> None:
    """Pagination limits the number of rows returned."""
    headers = await register_and_login(client)
    await upload_cv(client, headers, filename="cv1.pdf")
    await upload_cv(client, headers, filename="cv2.pdf")

    response = await client.get("/cvs/?limit=1", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_list_cvs_rejects_invalid_limit(client: AsyncClient) -> None:
    """A limit outside the allowed range fails validation."""
    headers = await register_and_login(client)

    response = await client.get("/cvs/?limit=0", headers=headers)

    assert response.status_code == 422


async def test_get_cv(client: AsyncClient) -> None:
    """A specific CV can be retrieved."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers, filename="mycv.pdf")

    response = await client.get(f"/cvs/{cv_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["filename"] == "mycv.pdf"


async def test_get_cv_not_found(client: AsyncClient) -> None:
    """An unknown CV returns 404."""
    headers = await register_and_login(client)

    response = await client.get("/cvs/999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == DEFAULT_ERROR_CV_NOT_FOUND


async def test_get_cv_belonging_to_another_user(client: AsyncClient) -> None:
    """Another user's CV is indistinguishable from one that does not exist."""
    owner_headers = await register_and_login(client, email="owner@example.com")
    cv_id = await upload_cv(client, owner_headers)
    intruder_headers = await register_and_login(client, email="intruder@example.com")

    response = await client.get(f"/cvs/{cv_id}", headers=intruder_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == DEFAULT_ERROR_CV_NOT_FOUND


async def test_delete_cv(client: AsyncClient, upload_dir: Path) -> None:
    """Deleting a CV removes both the record and the stored file."""
    headers = await register_and_login(client)
    cv_id = await upload_cv(client, headers)
    assert len(list(upload_dir.iterdir())) == 1

    response = await client.delete(f"/cvs/{cv_id}", headers=headers)

    assert response.status_code == 204
    assert list(upload_dir.iterdir()) == []
    assert (await client.get(f"/cvs/{cv_id}", headers=headers)).status_code == 404


async def test_version_is_not_reused_after_a_delete(client: AsyncClient) -> None:
    """A new upload never takes the version number of a CV that still exists."""
    headers = await register_and_login(client)
    first = await upload_cv(client, headers)
    await upload_cv(client, headers)
    await client.delete(f"/cvs/{first}", headers=headers)

    await upload_cv(client, headers)

    listed = (await client.get("/cvs/", headers=headers)).json()
    assert sorted(cv["version"] for cv in listed) == [2, 3]


async def test_delete_cv_belonging_to_another_user(
    client: AsyncClient, upload_dir: Path
) -> None:
    """A user cannot delete someone else's CV."""
    owner_headers = await register_and_login(client, email="owner@example.com")
    cv_id = await upload_cv(client, owner_headers)
    intruder_headers = await register_and_login(client, email="intruder@example.com")

    response = await client.delete(f"/cvs/{cv_id}", headers=intruder_headers)

    assert response.status_code == 404
    assert len(list(upload_dir.iterdir())) == 1


async def test_upload_cv_no_auth(client: AsyncClient) -> None:
    """Uploading without a token is rejected."""
    response = await client.post(
        "/cvs/",
        files={"file": ("cv.pdf", BytesIO(MINIMAL_PDF), "application/pdf")},
    )

    assert response.status_code == 401
