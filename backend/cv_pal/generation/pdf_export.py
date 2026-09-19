"""Writing the tailored CV as a PDF.

The third renderer over the one block model, alongside Markdown and DOCX. **DOCX is
still the format to submit where a choice exists** — it is structured data an applicant
tracking system reads directly, where a PDF is a page description it has to reconstruct.
PDF is here because it is what a *human* opens, it is what many portals accept, and a
handful still demand it.

ReportLab rather than the alternatives, and the reasons are the deployment story's:

- **WeasyPrint** renders HTML and CSS, which would be the nicest authoring model, and
  needs cairo and pango installed on the host. A self-hosted app that requires system
  libraries loses the users this project is for.
- **fpdf2** is smaller and LGPL. Importing it is fine, but it puts obligations on anyone
  redistributing, which is friction an MIT project does not need to take on.
- **ReportLab** is BSD, pure Python, and emits real extractable text — which is the only
  property that decides whether a parser can read the result at all.

## Staying readable to a machine

The same rules as the DOCX, for the same reason — the generator must not produce what
`analysis.parseability` would flag:

- **Real text, one column, in reading order.** A PDF can place glyphs anywhere; this one
  lays out a single linear story, so extraction order is document order.
- **Core fonts only.** Helvetica is one of the fourteen fonts every reader has, so
  nothing is embedded and nothing is substituted. A subsetted or exotic font is a common
  reason extracted text comes out as mojibake.
- **No tables, no columns, no images, no headers or footers.**

`tests/test_generation.py` pins this by extracting the text back out with `pypdf` — the
same reader the app uses on uploads — and running the project's own parseability check
over it. If the output ever stops being readable, the suite says so.
"""

import io
from collections.abc import Sequence
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate

from cv_pal.generation.tailored_cv import Block, BlockKind

_BASE = ParagraphStyle(
    "cvpal-body",
    fontName="Helvetica",
    fontSize=10,
    leading=14,
    alignment=TA_LEFT,
    spaceAfter=6,
)

# One style per block kind, so the mapping from meaning to appearance lives in one place
# and matches what the DOCX does with heading levels.
_STYLES: dict[BlockKind, ParagraphStyle] = {
    BlockKind.NAME: ParagraphStyle(
        "cvpal-name", parent=_BASE, fontName="Helvetica-Bold", fontSize=18, leading=22
    ),
    BlockKind.HEADLINE: ParagraphStyle(
        "cvpal-headline", parent=_BASE, fontSize=11, textColor="#444444"
    ),
    BlockKind.CONTACT: ParagraphStyle(
        "cvpal-contact", parent=_BASE, fontSize=9, textColor="#444444", spaceAfter=12
    ),
    BlockKind.SECTION: ParagraphStyle(
        "cvpal-section",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        spaceBefore=12,
        spaceAfter=4,
    ),
    BlockKind.ENTRY: ParagraphStyle(
        "cvpal-entry",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=11,
        spaceBefore=8,
        spaceAfter=2,
    ),
    BlockKind.META: ParagraphStyle(
        "cvpal-meta", parent=_BASE, fontSize=9, textColor="#444444", spaceAfter=4
    ),
    BlockKind.BODY: _BASE,
}


def render_pdf(blocks: Sequence[Block]) -> bytes:
    """Render the document as a PDF file.

    Args:
        blocks: The document, from `tailored_cv`.

    Returns:
        The file's bytes.
    """
    stream = io.BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        # Written into the PDF's own metadata, which is what a reader shows in its title
        # bar and what some portals index. Fixed text, not the user's.
        title="Curriculum Vitae",
    )
    document.build(
        [Paragraph(_markup_safe(block.text), _STYLES[block.kind]) for block in blocks]
    )
    return stream.getvalue()


def _markup_safe(text: str) -> str:
    """Escape text that ReportLab would otherwise read as markup.

    **Not cosmetic.** `Paragraph` parses its input as a small HTML dialect, so a profile
    containing `C++ & <legacy>` either renders wrongly or raises mid-build — and the
    content here is entirely user-supplied, which is exactly the case where "it will
    probably be fine" is wrong. Escaping is done once, at the only point where text
    enters ReportLab.

    Args:
        text: A block's text.

    Returns:
        The same text, with the three markup characters escaped.
    """
    return escape(text)


__all__ = ["render_pdf"]
