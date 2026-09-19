"""Proposing which roles evidence which skills, from the words the roles already carry.

No language model, and — like `extraction` — **no writes**. A skill named in a role's
own description is a claim that role can back, so the citation the profile needs is
usually already sitting in text the user wrote. This finds those, the user confirms
them, and only then does anything reach the database.

Why it matters: `Skill.is_evidenced` is what a tailored CV consults before it will
claim a skill, so an unevidenced skill is invisible to the whole generation path. Import
a CV and twenty skills arrive at once with no citations; without this the only way to
make them usable is twenty manual link operations, which is where people stop.

The match is deliberately conservative. It reads tokens rather than substrings, so "Go"
does not match "going" and "R" does not match every word containing one — a wrong
suggestion costs a click to ignore, but a plausible wrong one that gets confirmed puts
an unbacked claim on a CV, which is the failure this project exists to avoid.
"""

from dataclasses import dataclass

from cv_pal.analysis.keywords import canonical, tokenise


@dataclass(frozen=True, slots=True)
class SkillFacts:
    """A skill as the matcher reads it."""

    id: int
    name: str
    canonical_name: str


@dataclass(frozen=True, slots=True)
class ExperienceFacts:
    """A role, and the text it offers as evidence."""

    id: int
    title: str
    organisation: str
    description: str | None


@dataclass(frozen=True, slots=True)
class EvidenceSuggestion:
    """Roles that name a skill the profile does not yet cite for it."""

    skill_id: int
    experience_ids: tuple[int, ...]


def _terms(text: str) -> set[str]:
    """Reduce text to the canonical terms it mentions.

    Shares `tokenise` with the keyword analysis rather than splitting on its own: the
    rule that "node.js" is one token but the full stop ending a sentence is not part of
    it lives in one place, and rewriting it here is how "K8s." stops matching K8s.

    Args:
        text: Any prose.

    Returns:
        Canonical forms of every token, so "K8s" in a description matches a skill
        stored as "Kubernetes".
    """
    return {canonical(token) for token in tokenise(text)}


def _mentions(skill: SkillFacts, role: ExperienceFacts) -> bool:
    """Report whether a role's own words name this skill.

    Multi-word skills are checked as a phrase as well as by their parts: "machine
    learning" should not be evidenced by a role that says "machine" in one sentence and
    "learning" in another.

    Args:
        skill: The skill being looked for.
        role: The role that might evidence it.

    Returns:
        True when the role's title or description names the skill.
    """
    text = f"{role.title} {role.description or ''}".casefold()
    wanted = skill.canonical_name.casefold()

    if " " in wanted:
        return wanted in text or skill.name.casefold() in text
    return wanted in _terms(text)


def suggest_evidence(
    skills: tuple[SkillFacts, ...],
    experiences: tuple[ExperienceFacts, ...],
    *,
    already_cited: dict[int, frozenset[int]],
) -> tuple[EvidenceSuggestion, ...]:
    """Propose citations for skills whose roles already name them.

    Args:
        skills: The profile's skills.
        experiences: The profile's roles.
        already_cited: Experience ids each skill already cites, keyed by skill id. Those
            are excluded so a suggestion is always something new to confirm.

    Returns:
        One entry per skill with at least one uncited role naming it, in the order the
        skills were given. Skills with nothing to propose are left out entirely.
    """
    suggestions: list[EvidenceSuggestion] = []
    for skill in skills:
        cited = already_cited.get(skill.id, frozenset())
        found = tuple(
            role.id
            for role in experiences
            if role.id not in cited and _mentions(skill, role)
        )
        if found:
            suggestions.append(
                EvidenceSuggestion(skill_id=skill.id, experience_ids=found)
            )
    return tuple(suggestions)
