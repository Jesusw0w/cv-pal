import uuid
from pathlib import Path

import anyio
from fastapi import UploadFile

from cv_pal.config import get_settings
from cv_pal.constants import (
    DEFAULT_ALLOWED_EXTENSIONS,
    DEFAULT_ERROR_FILE_CONTENT_MISMATCH,
    DEFAULT_ERROR_FILE_TOO_LARGE,
    DEFAULT_ERROR_FILE_TYPE_NOT_ALLOWED,
    DEFAULT_ERROR_NO_FILENAME,
    DEFAULT_MAGIC_BYTES,
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_UPLOAD_CHUNK_SIZE,
)
from cv_pal.exceptions import FileTooLargeError, ValidationError


def validate_upload_name(filename: str | None) -> str:
    """Validate an upload's declared filename and return its extension.

    Args:
        filename: The client-supplied filename.

    Returns:
        The lowercased file extension, including the leading dot.

    Raises:
        ValidationError: If the filename is missing or the extension is not allowed.
    """
    if not filename:
        raise ValidationError(DEFAULT_ERROR_NO_FILENAME)

    suffix = Path(filename).suffix.lower()
    if suffix not in DEFAULT_ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(DEFAULT_ALLOWED_EXTENSIONS))
        raise ValidationError(
            DEFAULT_ERROR_FILE_TYPE_NOT_ALLOWED.format(allowed=allowed)
        )
    return suffix


def _verify_magic_bytes(suffix: str, head: bytes) -> None:
    """Verify a file's leading bytes match the type its extension claims.

    Args:
        suffix: The file extension, including the leading dot.
        head: The first bytes of the file.

    Raises:
        ValidationError: If the content does not match the extension.
    """
    expected = DEFAULT_MAGIC_BYTES.get(suffix)
    if expected is not None and not head.startswith(expected):
        raise ValidationError(DEFAULT_ERROR_FILE_CONTENT_MISMATCH)


async def save_upload(file: UploadFile, *, upload_dir: Path | None = None) -> Path:
    """Stream an uploaded file to disk under a generated name.

    The storage key is generated server-side, so a hostile filename can never escape
    the upload directory. The size limit is enforced while writing rather than after
    reading, so an oversized upload never has to fit in memory.

    Args:
        file: The uploaded file.
        upload_dir: Directory to write into; defaults to the configured upload
            directory, resolved at call time so it follows configuration.

    Returns:
        The path the file was written to.

    Raises:
        ValidationError: If the filename, type, content or size is invalid.
    """
    suffix = validate_upload_name(file.filename)
    target_dir = upload_dir if upload_dir is not None else get_settings().upload_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / f"{uuid.uuid4()}{suffix}"

    written = 0
    checked_magic = False
    try:
        async with await anyio.open_file(destination, "wb") as target:
            while chunk := await file.read(DEFAULT_UPLOAD_CHUNK_SIZE):
                if not checked_magic:
                    _verify_magic_bytes(suffix, chunk)
                    checked_magic = True

                written += len(chunk)
                if written > DEFAULT_MAX_FILE_SIZE:
                    size_mb = DEFAULT_MAX_FILE_SIZE // (1024 * 1024)
                    raise FileTooLargeError(
                        DEFAULT_ERROR_FILE_TOO_LARGE.format(size_mb=size_mb)
                    )
                await target.write(chunk)
    except ValidationError:
        destination.unlink(missing_ok=True)
        raise

    return destination


async def delete_file(file_path: Path) -> None:
    """Delete a stored file if it still exists.

    Args:
        file_path: Path to the file to remove.
    """
    await anyio.to_thread.run_sync(lambda: file_path.unlink(missing_ok=True))
