"""File upload validation utilities.

INJ-05 / API-06 fix: centralized upload validation with
extension, MIME type, and magic-byte signature checks.
"""
from __future__ import annotations

from fastapi import HTTPException, UploadFile

# ── Constants ──

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_RESUME_EXTS = {"pdf", "docx", "doc"}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/msword",  # doc
}

# Magic-byte signatures for content-type verification
# P0-AUDIT-FIX (2026-08-13): previously .doc had NO magic-byte entry, so an
# attacker uploading HTML/JS/PDF disguised as .doc would silently bypass the
# mismatch check and feed poisoned text into the resume extraction pipeline.
# .doc (legacy OLE2 Compound File) starts with the canonical OLE2 header
# `D0 CF 11 E0 A1 B1 1A E1`. Add it to the signature table.
_FILE_SIGNATURES: dict[bytes, str] = {
    b"%PDF": "pdf",
    b"PK": "docx",  # ZIP-based (docx is a ZIP archive)
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": "doc",  # OLE2 Compound File
}


async def validate_resume_upload(file: UploadFile, *, max_size: int = MAX_UPLOAD_SIZE) -> bytes:
    """Validate an uploaded resume file and return its content bytes.

    Checks (in order):
    1. Filename presence and extension whitelist
    2. Content-Type (MIME) whitelist
    3. File size limit
    4. Magic-byte signature vs extension mismatch

    Raises HTTPException on any validation failure.
    """
 # 1. Filename + extension
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_RESUME_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Supported: .pdf, .docx, .doc",
        )

 # 2. MIME type
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported MIME type: {file.content_type}",
        )

 # 3. Size limit
    content_bytes = await file.read(max_size + 1)
    if len(content_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {max_size // 1024 // 1024} MB)",
        )

 # 4. Magic-byte signature — prevent extension spoofing
 # P0-AUDIT-FIX (2026-08-13): the previous logic only raised when a
 # signature MATCHED but did not match the extension. If the extension
 # itself was unrecognised (e.g. .doc without OLE2 header), `_detected`
 # stayed None and the upload slipped through. Now: ANY non-PDF/DOCX
 # extension must hit its registered signature, otherwise reject.
    if content_bytes:
        _detected: str | None = None
        for sig, fmt in _FILE_SIGNATURES.items():
            if content_bytes.startswith(sig):
                _detected = fmt
                break
 # Mismatch: detected format != claimed extension -> reject.
        if _detected and _detected != ext:
            raise HTTPException(
                status_code=400,
                detail=f"File content ({_detected}) does not match extension (.{ext})",
            )
 # No signature matched but extension IS in our allow-list and
 # requires a signature (.doc/.docx/.pdf). Reject unrecognised content.
        if _detected is None and ext in {"pdf", "docx", "doc"}:
            raise HTTPException(
                status_code=400,
                detail=f"File content does not match any known {ext} signature; "
                       f"refusing to process potentially malformed file",
            )

 # Reset file position for downstream reading
    await file.seek(0)
    return content_bytes
