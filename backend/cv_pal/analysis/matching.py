"""Scoring a job posting against what the user has and what they want.

Deterministic, per principle 1: the same posting, profile and goals always produce
the same score, and no language model is involved. A model's only planned job here is
the prose rationale — the number, and every reason behind it, is computed.

Two distinct mechanisms, and keeping them apart is the point (principle 8):

- **Non-negotiables filter.** A posting that breaks one is *blocked*, not merely
  penalised, and the block names which one. A user who said "remote only" should not be
  shown a 74% match in Munich.
- **Preferences score.** Everything else contributes points with a stated reason, so the
  number can always be read back as a sentence.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from cv_pal.analysis.keywords import analyse, canonical
from cv_pal.constants import (
    DEFAULT_LOCATION_NOISE_TERMS as LOCATION_NOISE_TERMS,
)
from cv_pal.constants import (
    DEFAULT_UNRESTRICTED_LOCATION_TERMS as UNRESTRICTED_LOCATION_TERMS,
)
from cv_pal.constants import WorkRegime

# Relative weight of each component. Keyword coverage dominates because it is the one
# measured against evidence rather than against a stated preference.
_COVERAGE_WEIGHT = 0.6
_TITLE_WEIGHT = 0.2
_REGIME_WEIGHT = 0.1
_LOCATION_WEIGHT = 0.1

_NOT_SCORED = " — not scored"

_REGIME_MARKERS: dict[WorkRegime, tuple[str, ...]] = {
    WorkRegime.REMOTE: ("remote", "work from home", "distributed", "anywhere"),
    WorkRegime.HYBRID: ("hybrid", "flexible working", "days in the office"),
    WorkRegime.ON_SITE: ("on-site", "on site", "onsite", "in office", "in-office"),
}

_WORD = re.compile(r"[a-z0-9+#./-]+")
# Case-preserving, because a place's own spelling is shown back to the user. Letters
# only: a location line's digits are timezone offsets, never a place.
_PLACE_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class MatchReason:
    """One component of a score, phrased so it can be shown to the user."""

    label: str
    detail: str


@dataclass(frozen=True, slots=True)
class _Component:
    """One weighted input to the score, or one that could not be judged.

    ``fit`` is None when there was nothing to judge against — the user has not stated
    the preference, or the posting does not mention it. Such a component contributes
    nothing and takes no weight, rather than scoring full marks.
    """

    weight: float
    fit: float | None
    label: str
    detail: str


@dataclass(frozen=True, slots=True)
class MatchScore:
    """How well a posting fits, and why.

    Attributes:
        score: 0-100. Zero when blocked: a blocked posting has no useful ranking
            against the ones that are not.
        blocked_by: The non-negotiable the posting breaks, or None.
        reasons: The components, best first.
        missing_required: Terms the posting requires that the profile cannot evidence.
        preference_rank: Where the posting's arrangement sits in the user's ordered
            work regimes, for sorting before the score: 0 offers their first choice,
            1 their second, and so on; then postings that do not say; then ones that
            offer only arrangements the user did not choose. 0 for everything when the
            user has not chosen any.
    """

    score: int
    blocked_by: str | None = None
    reasons: tuple[MatchReason, ...] = field(default_factory=tuple)
    missing_required: tuple[str, ...] = field(default_factory=tuple)
    preference_rank: int = 0


def detect_regimes(text: str) -> frozenset[WorkRegime]:
    """Read the work arrangements a posting mentions.

    Args:
        text: The posting's title, location and description.

    Returns:
        The regimes named. Empty when the posting does not say, which is common and is
        treated as "unknown" rather than as a mismatch.
    """
    lowered = text.casefold()
    return frozenset(
        regime
        for regime, markers in _REGIME_MARKERS.items()
        if any(marker in lowered for marker in markers)
    )


def _place_words(text: str) -> dict[str, str]:
    """Reduce a location line to the words that actually name a place.

    Args:
        text: A location line, from either a posting or the user's goals.

    Returns:
        Each narrowing word folded for comparison, mapped to the spelling the source
        used. Empty when the line names nowhere — which is what `Remote` on its own
        does, and is a different answer from naming a place the user cannot be.

        The original spelling is kept because these are shown back to the user and
        places are not uniformly capitalised: re-casing turns `USA` into `Usa` and
        `EMEA` into `Emea`. Only the comparison is case-insensitive.
    """
    found: dict[str, str] = {}
    for word in _PLACE_WORD.findall(text):
        folded = word.casefold()
        if folded in LOCATION_NOISE_TERMS or folded.isdigit():
            continue
        found.setdefault(folded, word)
    return found


def _same_place(left: str, right: str) -> bool:
    """Report whether two place words plausibly name the same place.

    Prefix rather than equality, because feeds inflect the same place freely: `Europe`
    and `European`, `America` and `Americas`. Two letters is the floor so `UK` and `US`
    still work.

    Args:
        left: One place word.
        right: The other.

    Returns:
        True when either is a prefix of the other.

    Note:
        Prefix matching over-matches on words that share a stem and do not share a
        place — `India` against `Indiana` is the clearest. It is accepted because the
        cost is asymmetric: over-matching shows a posting the user can dismiss, and
        under-matching hides a job they could have taken.
    """
    return left.startswith(right) or right.startswith(left)


def location_fit(
    posting_location: str | None, work_locations: list[str]
) -> tuple[float | None, str, dict[str, str]]:
    """Judge whether the user may work where a posting requires them to be.

    **No geography is inferred.** The app does not assert that Portugal is in Europe, or
    that EMEA contains either — it compares the user's own stated terms against the
    posting's. The same rule PLANNING applies to the skills alias map applies here: the
    project has no authoritative containment data, and approximating it would silently
    hide jobs on a guess about the world. So the goals screen asks the user to list the
    regions they can work in, which is a fact they know and we do not.

    Args:
        posting_location: The posting's location line, when it has one.
        work_locations: Places the user said they can work from.

    Returns:
        A fit from 0.0 to 1.0, a sentence explaining it, and the posting's place words
        (empty when it named nowhere, which callers use to decide whether to block).

        The fit is **None** when there was nothing to judge: the posting named nowhere,
        or the user has not said where they can work. That is different from a perfect
        fit, and scoring it as one handed every posting free marks.
    """
    stated = _place_words(posting_location or "")

    if not stated:
        return None, "The posting does not say where you have to be.", stated
    if stated.keys() & UNRESTRICTED_LOCATION_TERMS:
        return 1.0, "Open to candidates anywhere.", stated
    if not work_locations:
        return None, "You have not said where you can work.", stated

    wanted = {word for entry in work_locations for word in _place_words(entry)}
    shared = sorted(
        word for word in stated if any(_same_place(word, mine) for mine in wanted)
    )
    if shared:
        named = _readable(_shortest_stems(shared), stated)
        return 1.0, f"Open to {named}, where you said you can work.", stated

    return (
        0.0,
        f"Requires {_readable(sorted(stated), stated)}, which is not where you said "
        "you can work.",
        stated,
    )


def _shortest_stems(words: list[str]) -> list[str]:
    """Drop words that only repeat a shorter one already present.

    A posting saying "Europe, European timezones" matches on both `europe` and
    `european`, and reading "Open to europe, european" back to the user is noise. The
    shorter word is kept because it is the one they are likelier to have typed.

    Args:
        words: Matched place words, sorted.

    Returns:
        The same list without words that extend another entry.
    """
    return [
        word
        for word in words
        if not any(other != word and word.startswith(other) for other in words)
    ]


def _readable(words: list[str], spellings: dict[str, str]) -> str:
    """Render place words as a sentence fragment.

    Args:
        words: Folded place words to render.
        spellings: Folded word to the spelling its source used.

    Returns:
        Comma-joined, each in the source's own capitalisation, so `USA` and `EMEA`
        survive intact.
    """
    return ", ".join(spellings.get(word, word) for word in words)


def title_match(title: str, target_roles: list[str]) -> float:
    """Score how well a posting's title matches the roles the user is aiming at.

    Public because board sync reuses it to decide what is worth saving: "this is one of
    the jobs I am looking for" has to mean the same thing at save time as it does when
    the posting is ranked later.

    Compares word sets rather than whole strings: "Senior Backend Engineer" should match
    a target of "Backend Engineer", and an exact-string comparison never would.

    Args:
        title: The posting's title.
        target_roles: The user's target role titles.

    Returns:
        0.0 to 1.0. Returns 1.0 when no targets are set — an unstated preference cannot
        be failed, and scoring it as zero would rank every posting equally badly.
    """
    if not target_roles:
        return 1.0

    title_words = {canonical(word) for word in _WORD.findall(title.casefold())}
    if not title_words:
        return 0.0

    best = 0.0
    for role in target_roles:
        role_words = {canonical(word) for word in _WORD.findall(role.casefold())}
        if role_words:
            best = max(best, len(title_words & role_words) / len(role_words))
    return min(best, 1.0)


def score_posting(
    *,
    title: str,
    description: str,
    location: str | None,
    profile_text: str,
    target_roles: list[str],
    work_regimes: list[WorkRegime],
    regime_non_negotiable: bool,
    work_locations: list[str] | None = None,
    location_non_negotiable: bool = False,
    company: str | None = None,
) -> MatchScore:
    """Score one posting.

    Args:
        title: The posting's title.
        description: The posting's text.
        location: The posting's location, when it gives one.
        company: The hiring company, so its own name is not reported as a missing skill.
        profile_text: The user's evidenced skills and experience, as text.
        target_roles: Roles the user is aiming at.
        work_regimes: Acceptable arrangements, best first.
        regime_non_negotiable: Whether a regime mismatch blocks rather than penalises.
        work_locations: Places the user said they can work from.
        location_non_negotiable: Whether being outside them blocks rather than scores.

    Returns:
        The score with its reasons.
    """
    haystack = f"{title} {location or ''} {description}"
    mentioned = detect_regimes(haystack)

    # Blocks only when the posting says what its arrangement is: refusing the silent
    # ones would hide most of the market on a technicality.
    blocks = regime_non_negotiable and work_regimes and mentioned
    if blocks and not mentioned & set(work_regimes):
        named = ", ".join(
            sorted(regime.value.replace("_", " ") for regime in mentioned)
        )
        return MatchScore(
            score=0,
            blocked_by=f"You ruled this out: the posting is {named}.",
            preference_rank=len(work_regimes) + 1,
        )

    places = work_locations or []
    place_fit, place_detail, stated_places = location_fit(location, places)

    # Same rule as the regime block: silence is not evidence. Only a posting that
    # named somewhere, and nowhere the user can work, is ruled out.
    if location_non_negotiable and places and stated_places and place_fit == 0.0:
        return MatchScore(
            score=0,
            blocked_by=(
                "You ruled this out: it requires "
                f"{_readable(sorted(stated_places), stated_places)}."
            ),
            preference_rank=len(work_regimes) + 1,
        )

    coverage = analyse(profile_text, description, company=company)

    regime_fit: float | None = None
    regime_detail = "The posting does not say how the work is arranged."
    # Unstated sorts after every arrangement the user chose, not-chosen after that.
    preference_rank = len(work_regimes) if work_regimes else 0
    if mentioned:
        if not work_regimes:
            regime_detail = "You have not said which arrangements suit you."
        elif mentioned & set(work_regimes):
            preference_rank = min(
                work_regimes.index(regime) for regime in mentioned & set(work_regimes)
            )
            best = work_regimes[preference_rank].value.replace("_", " ")
            regime_fit = 1.0
            if len(work_regimes) == 1:
                regime_detail = f"Offers {best}, which you said suits you."
            elif preference_rank == 0:
                regime_detail = f"Offers {best}, your first choice."
            else:
                regime_detail = (
                    f"Offers {best}, your {_ordinal(preference_rank + 1)} choice; "
                    "postings offering one you prefer are listed first."
                )
        else:
            preference_rank = len(work_regimes) + 1
            regime_fit = 0.0
            regime_detail = "The arrangement is not one you said suits you."

    title_fit = title_match(title, target_roles) if target_roles else None

    components = (
        _Component(
            weight=_COVERAGE_WEIGHT,
            fit=coverage.score / 100,
            label=f"Skills {coverage.score}/100",
            detail=(
                f"Your profile evidences {len(coverage.matched)} of "
                f"{len(coverage.matched) + len(coverage.missing)} terms it uses."
            ),
        ),
        _Component(
            weight=_TITLE_WEIGHT,
            fit=title_fit,
            label=(
                f"Title {round(title_fit * 100)}/100"
                if title_fit is not None
                else f"Title{_NOT_SCORED}"
            ),
            detail=(
                f'"{title}" against the roles you are targeting.'
                if target_roles
                else "You have not set any target roles yet."
            ),
        ),
        _Component(
            weight=_REGIME_WEIGHT,
            fit=regime_fit,
            label=(
                "Work arrangement"
                if regime_fit is not None
                else f"Work arrangement{_NOT_SCORED}"
            ),
            detail=regime_detail,
        ),
        _Component(
            weight=_LOCATION_WEIGHT,
            fit=place_fit,
            label=(
                "Where you can work"
                if place_fit is not None
                else f"Where you can work{_NOT_SCORED}"
            ),
            detail=place_detail,
        ),
    )

    return MatchScore(
        score=_assessed_score(components),
        reasons=tuple(MatchReason(label=c.label, detail=c.detail) for c in components),
        missing_required=tuple(k.term for k in coverage.missing_required),
        preference_rank=preference_rank,
    )


def _ordinal(number: int) -> str:
    """Spell a small position: 2 -> "second". There are only three regimes."""
    return {1: "first", 2: "second", 3: "third"}.get(number, f"{number}th")


class Ranked(Protocol):
    """Anything carrying what postings are ordered by: a match, or a summary of one."""

    @property
    def blocked_by(self) -> str | None:
        """The non-negotiable broken, if any."""
        ...

    @property
    def preference_rank(self) -> int:
        """See `MatchScore.preference_rank`."""
        ...

    @property
    def score(self) -> int:
        """0-100."""
        ...


def ranking_key(match: Ranked) -> tuple[bool, int, int]:
    """Order postings: allowed first, preferred arrangement next, then best score.

    The preference sorts before the score rather than being folded into it: someone who
    said "remote, then hybrid" wants every remote posting above every hybrid one, and
    a weight inside the score would let a strong hybrid match overtake a weak remote.

    Args:
        match: A posting's match.

    Returns:
        The sort key; smaller sorts first.
    """
    return (match.blocked_by is not None, match.preference_rank, -match.score)


def _assessed_score(components: Sequence[_Component]) -> int:
    """Combine only the components that could actually be judged.

    An unstated preference used to score 1.0, so a brand-new user with no goals was
    handed the title, arrangement and location weight for free: an empty profile scored
    **40/100 against every posting**, and the ranking collapsed to a constant. The
    per-reason text was honest while the headline number was not, and the number is what
    people read.

    Dropping the component and renormalising over the rest means the score only ever
    reports what was measured. The cost is that a user with no profile and no goals now
    sees 0 everywhere — which is the true answer, and the reasons name what to fill in.

    Args:
        components: Every component, judged or not.

    Returns:
        0-100 over the judged components, or 0 when nothing could be judged.
    """
    judged = [
        (component.weight, fit)
        for component in components
        if (fit := component.fit) is not None
    ]
    total = sum(weight for weight, _ in judged)
    if not total:
        return 0
    return round(100 * sum(weight * fit for weight, fit in judged) / total)
