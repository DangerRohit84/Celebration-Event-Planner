"""Test helpers for building small, valid PDF documents.

The uploads endpoint really parses PDFs, so the tests need genuine files
rather than a magic-byte stub. This module builds a minimal but standards
compliant PDF (correct xref table, embedded Helvetica font, one text
stream per page) whose text ``pypdf`` can extract.
"""

from __future__ import annotations


def build_pdf(pages: list[list[str]]) -> bytes:
    """Build a valid PDF whose pages carry the given text lines.

    Args:
        pages: One list of text lines per page.

    Returns:
        The raw bytes of the generated PDF document.
    """
    objects: list[bytes] = []
    page_count = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(page_count))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    font_obj = 3 + 2 * page_count
    for i, lines in enumerate(pages):
        page_obj = 3 + 2 * i
        content_obj = page_obj + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode(),
        )
        stream_lines = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
        for line in lines:
            escaped = (
                line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            )
            stream_lines.append(f"({escaped}) Tj")
            stream_lines.append("T*")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1")
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream",
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_offset = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {count} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return bytes(out)


def build_text_pdf() -> bytes:
    """Build a one-page PDF describing a small wedding venue checklist.

    Returns:
        The raw bytes of the generated PDF document.
    """
    return build_pdf(
        [
            [
                "Venue Contract",
                "Sign the venue contract six weeks before the wedding date.",
                "Confirm the final guest count with the caterer.",
            ],
            [
                "Transport Rules",
                "Arrange shuttle transport for guests arriving late.",
            ],
        ],
    )


def build_scanned_pdf() -> bytes:
    """Build a PDF whose page carries no extractable text.

    The page exists but its content stream is empty, which is what a
    scanned image-only document looks like to a text extractor.

    Returns:
        The raw bytes of the generated PDF document.
    """
    return build_pdf([[]])
