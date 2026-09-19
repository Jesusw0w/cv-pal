"""Whether an applicant tracking system can actually read a CV.

The most expensive CV defects are mechanical, not editorial: a two-column layout that
extracts as interleaved nonsense, dates a parser cannot read, contact details inside a
header that never makes it into the text layer. A beautifully written CV that does not
survive extraction is rejected before a human sees it.

These checks run on the *extracted* text — the same text an ATS would work from — so
they measure what the parser sees rather than what the document looks like.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from cv_pal.analysis.vocabulary import ACTION_VERBS, EXPECTED_SECTIONS
from cv_pal.constants import (
    DEFAULT_CV_MAX_WORDS,
    DEFAULT_CV_MIN_WORDS,
    DEFAULT_SHORT_LINE_RATIO_LIMIT,
    DEFAULT_SHORT_LINE_WORDS,
    ParseabilitySeverity,
)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}")
# Machine-readable date forms: "2021", "03/2021", "2021-03", "Mar 2021", "March 2021".
_DATE = re.compile(
    r"\b(?:"
    r"(?:19|20)\d{2}"
    r"|\d{1,2}[/-](?:19|20)\d{2}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:19|20)\d{2}"
    r")\b",
    flags=re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*(?:[-•*▪◦·–—]|\d+[.)])\s+")  # noqa: RUF001  # dashes are real bullet glyphs
_QUANTITY = re.compile(r"\d+\s*(?:%|percent|k\b|m\b|bn\b|x\b)|\b\d[\d,.]*\b")


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing wrong, or worth knowing, about a CV's machine readability.

    Attributes:
        code: Stable identifier, safe to branch on in a UI.
        severity: How much it matters.
        message: Human-readable explanation.
    """

    code: str
    severity: ParseabilitySeverity
    message: str


@dataclass(frozen=True, slots=True)
class ParseabilityReport:
    """The outcome of the mechanical checks.

    Attributes:
        findings: Everything detected, most severe first.
        word_count: Words in the extracted text.
        score: 0 to 100, where 100 means nothing was found.
    """

    findings: tuple[Finding, ...]
    word_count: int
    score: int

    @property
    def blocking(self) -> tuple[Finding, ...]:
        """Return findings likely to get the CV rejected before a human reads it.

        Returns:
            Findings of ``ERROR`` severity.
        """
        return tuple(
            f for f in self.findings if f.severity is ParseabilitySeverity.ERROR
        )


def _detect_sections(lowered: str) -> list[str]:
    """Find which expected section headings are present.

    Args:
        lowered: The lowercased CV text.

    Returns:
        The names of the sections detected.
    """
    return [
        name
        for name, headings in EXPECTED_SECTIONS.items()
        if any(heading in lowered for heading in headings)
    ]


def _short_line_ratio(lines: Sequence[str]) -> float:
    """Measure how much of the text is fragmented into very short lines.

    A multi-column layout usually extracts as a large number of two- or three-word
    lines, so this is a workable proxy for "the parser saw columns".

    Args:
        lines: Non-empty lines of the CV.

    Returns:
        The fraction of lines that are suspiciously short, or 0 when there are none.
    """
    if not lines:
        return 0.0
    short = sum(1 for line in lines if len(line.split()) <= DEFAULT_SHORT_LINE_WORDS)
    return short / len(lines)


def check_parseability(cv_text: str) -> ParseabilityReport:
    """Assess whether an ATS can read this CV.

    Args:
        cv_text: Text extracted from the CV file.

    Returns:
        A report with findings, a word count, and a score out of 100.
    """
    findings: list[Finding] = []
    lines = [line.strip() for line in cv_text.splitlines() if line.strip()]
    words = cv_text.split()
    word_count = len(words)
    lowered = cv_text.casefold()

    if word_count == 0:
        return ParseabilityReport(
            findings=(
                Finding(
                    code="no_text",
                    severity=ParseabilitySeverity.ERROR,
                    message=(
                        "No text could be extracted. The file is probably a scan or "
                        "an image, which most applicant tracking systems discard "
                        "entirely."
                    ),
                ),
            ),
            word_count=0,
            score=0,
        )

    if not _EMAIL.search(cv_text):
        findings.append(
            Finding(
                code="no_email",
                severity=ParseabilitySeverity.ERROR,
                message=(
                    "No email address found in the extracted text. If it sits in a "
                    "page header or a text box, the parser will not see it and you "
                    "cannot be contacted."
                ),
            )
        )

    if not _PHONE.search(cv_text):
        findings.append(
            Finding(
                code="no_phone",
                severity=ParseabilitySeverity.INFO,
                message=(
                    "No phone number found. Optional, but many recruiters expect one."
                ),
            )
        )

    detected = _detect_sections(lowered)
    for missing in sorted(set(EXPECTED_SECTIONS) - set(detected)):
        findings.append(
            Finding(
                code=f"missing_section_{missing}",
                severity=ParseabilitySeverity.WARNING,
                message=(
                    f"No '{missing}' heading was detected. Parsers use headings to "
                    f"decide what each block of text means; unlabelled sections are "
                    f"often dropped."
                ),
            )
        )

    if not _DATE.search(cv_text):
        findings.append(
            Finding(
                code="no_parseable_dates",
                severity=ParseabilitySeverity.ERROR,
                message=(
                    "No machine-readable dates found. Use forms like '2021' or "
                    "'Mar 2021'; a parser cannot compute your years of experience "
                    "from 'two years ago'."
                ),
            )
        )

    ratio = _short_line_ratio(lines)
    if ratio > DEFAULT_SHORT_LINE_RATIO_LIMIT:
        findings.append(
            Finding(
                code="fragmented_layout",
                severity=ParseabilitySeverity.WARNING,
                message=(
                    f"{ratio:.0%} of lines are very short, which is what a "
                    f"multi-column or table layout looks like after extraction. "
                    f"Single-column layouts survive parsing far more reliably."
                ),
            )
        )

    if word_count < DEFAULT_CV_MIN_WORDS:
        findings.append(
            Finding(
                code="too_short",
                severity=ParseabilitySeverity.WARNING,
                message=(
                    f"Only {word_count} words extracted. Either the CV is very thin or "
                    f"most of its content did not survive extraction."
                ),
            )
        )
    elif word_count > DEFAULT_CV_MAX_WORDS:
        findings.append(
            Finding(
                code="too_long",
                severity=ParseabilitySeverity.INFO,
                message=(
                    f"{word_count} words is long for a non-academic CV; most reviewers "
                    f"expect around two pages."
                ),
            )
        )

    bullets = [line for line in lines if _BULLET.match(line)]
    if bullets:
        weak = [
            line
            for line in bullets
            if _BULLET.sub("", line).split()
            and _BULLET.sub("", line).split()[0].casefold() not in ACTION_VERBS
        ]
        if len(weak) > len(bullets) / 2:
            findings.append(
                Finding(
                    code="weak_bullet_verbs",
                    severity=ParseabilitySeverity.INFO,
                    message=(
                        f"{len(weak)} of {len(bullets)} bullets do not start with an "
                        f"action verb. 'Led', 'Built', 'Reduced' read as achievements; "
                        f"'Responsible for' reads as a job description."
                    ),
                )
            )

        # A date is not a metric: "Led the migration in March 2021" says nothing about
        # scale, so dates are removed before looking for numbers.
        unquantified = [
            line for line in bullets if not _QUANTITY.search(_DATE.sub("", line))
        ]
        if len(unquantified) > len(bullets) * 0.7:
            findings.append(
                Finding(
                    code="unquantified_bullets",
                    severity=ParseabilitySeverity.INFO,
                    message=(
                        f"{len(unquantified)} of {len(bullets)} bullets contain no "
                        f"numbers. Scale and outcome are what make achievements "
                        f"credible."
                    ),
                )
            )

    penalty = sum(finding.severity.penalty for finding in findings)
    score = max(0, 100 - penalty)

    findings.sort(key=lambda f: (-f.severity.penalty, f.code))
    return ParseabilityReport(
        findings=tuple(findings), word_count=word_count, score=score
    )
