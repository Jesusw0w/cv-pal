"""Assembling a cover letter from facts the profile already states.

## What this is, and what it is not

It is **a draft made of verified facts**, not a finished letter. Every sentence about
the user is copied from their profile; the only text this module authors is connective
structure and the posting's own title and company. Nothing is inferred, nothing is
embellished, and no model is involved.

It is **not** good prose, and the interface says so rather than implying otherwise. A
letter assembled from a fixed scaffold reads like one, and the honest thing to do is
hand the user a correct skeleton and tell them which part is theirs to write — not to
generate confident filler and let them discover in an interview that they cannot
defend a sentence they never wrote.

## Why the similarity check ships in the same commit

A deterministic scaffold produces letters that resemble each other. That is precisely
the property PLANNING's *self-similarity* check exists to surface, and shipping the
generator without the check would be the product doing the thing it says it is against:

> only a tool holding the whole application history can see that the last ten letters
> were 92% identical. That is spray-and-pray by definition, whatever produced the text.

So the check is not a safeguard bolted on afterwards; on a first draft it will read
high **by construction**, and that number is the correct message: *this is boilerplate
so far, make it specific*. As the user edits, it falls. That is the loop working, and
it is why `analysis.similarity` landed with this file rather than after it.

The rule from PLANNING applies here more than anywhere: **the system never optimises
for evading detection.** Nothing below is shaped to lower the similarity number. The
only thing that lowers it is the user actually writing something true about this job.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from cv_pal.generation.tailored_cv import ProfileFacts, Surfaced

# Fixed structural text. Named so the grounding test can allow exactly these and
# nothing else, the same way the CV renderer's label is.
_OPENING = "Dear Hiring Team,"
_APPLYING = "I am writing to apply for the role of"
_EVIDENCE_HEADING = "Where your requirements meet my experience:"
_CLOSING = "Kind regards,"
_PROMPT = (
    "[Write one paragraph here: why this company, and what about this role you want. "
    "Nothing else in this letter is specific to them, and a reader can tell.]"
)


@dataclass(frozen=True, slots=True)
class CoverLetterDraft:
    """A letter assembled from profile facts.

    Attributes:
        body: The draft.
        evidence: The requirement-to-role lines, so the interface can show what each
            claim rests on without re-deriving it.
        needs_writing: Whether the draft still contains the prompt for the paragraph
            only the user can write. A letter sent with that placeholder in it is the
            embarrassment the quality gate's data-completeness check exists to stop.
    """

    body: str
    evidence: tuple[str, ...] = field(default_factory=tuple)
    needs_writing: bool = True


def compose(
    facts: ProfileFacts,
    *,
    job_title: str,
    company: str | None,
    surfaced: Sequence[Surfaced],
) -> CoverLetterDraft:
    """Assemble the draft.

    Args:
        facts: The profile, the only permitted source of claims about the user.
        job_title: The posting's title. A fact about the job, not about the user.
        company: The hiring company, when known.
        surfaced: What the tailored CV brought forward, reused so the letter and the CV
            cannot disagree about which requirements the user evidences.

    Returns:
        The draft.
    """
    where = f"{job_title} at {company}" if company else job_title
    lines: list[str] = [_OPENING, "", f"{_APPLYING} {where}."]

    if facts.summary:
        lines += ["", facts.summary]

    # One line per requirement the user can back, naming the role that backs it.
    # Every word of it is either the posting's or the profile's.
    evidence = tuple(
        f"- {item.skill}: {item.evidence[0]}" for item in surfaced if item.evidence
    )
    if evidence:
        lines += ["", _EVIDENCE_HEADING, "", *evidence]

    lines += ["", _PROMPT]

    signature = [part for part in (facts.full_name, facts.email) if part]
    lines += ["", _CLOSING, *signature]

    return CoverLetterDraft(
        body="\n".join(lines).strip() + "\n",
        evidence=evidence,
        needs_writing=True,
    )


def contains_prompt(body: str) -> bool:
    """Report whether a letter still has the unwritten paragraph in it.

    Args:
        body: The letter.

    Returns:
        True when the placeholder survives. Checked on save rather than only on
        generation, because the text that gets sent is the edited one.
    """
    return _PROMPT in body


__all__ = ["CoverLetterDraft", "compose", "contains_prompt"]
