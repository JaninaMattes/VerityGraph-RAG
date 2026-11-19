"""Write a minimal text PDF (one page per list of lines) without a PDF library."""


def text_pdf(pages: list[list[str]]) -> bytes:
    """Return the bytes of a PDF with Helvetica text, 16 pt line spacing."""
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [{}] /Count {} >>".format(
            " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages))), len(pages)
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, lines in enumerate(pages):
        escaped = (
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            for line in lines
        )
        stream = "\n".join(
            ["BT", "/F1 12 Tf", "72 720 Td", "16 TL"]
            + [f"({line}) Tj T*" for line in escaped]
            + ["ET"]
        )
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")

    output = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(output)
    output += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    output += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    output += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return output
