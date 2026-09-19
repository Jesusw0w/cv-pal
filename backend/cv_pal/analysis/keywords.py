"""Keyword extraction and coverage scoring.

Entirely deterministic: the same CV and job description always produce the same report.
No model is involved, which makes this reproducible, free to run, instant, and testable
— and it means the majority of the product's value works with no LLM configured at all.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from cv_pal.analysis.vocabulary import (
    JOB_POSTING_BOILERPLATE,
    KNOWN_PHRASES,
    KNOWN_TERMS,
    PREFERRED_MARKERS,
    REQUIRED_MARKERS,
    SKILL_ALIASES,
    STOPWORDS,
)
from cv_pal.constants import (
    DEFAULT_KEYWORD_MAX_PHRASE_WORDS,
    DEFAULT_KEYWORD_MIN_LENGTH,
    DEFAULT_PREFERRED_KEYWORD_WEIGHT,
    DEFAULT_REQUIRED_KEYWORD_WEIGHT,
)

# Keeps intra-word punctuation that carries meaning in tech terms: node.js, ci/cd,
# .net, c++, test-driven. Splitting on those would destroy the term.
_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#./\-]*", flags=re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Keyword:
    """A term drawn from a job description.

    Attributes:
        term: The canonical, lowercased form.
        required: Whether the posting presents it as a hard requirement.
        occurrences: How many times it appeared, a rough proxy for emphasis.
    """

    term: str
    required: bool
    occurrences: int = 1

    @property
    def weight(self) -> float:
        """Return the term's contribution to the coverage score.

        Required terms count for more, and repetition raises a term's weight with
        diminishing returns rather than linearly.

        Returns:
            A positive weight.
        """
        base = (
            DEFAULT_REQUIRED_KEYWORD_WEIGHT
            if self.required
            else DEFAULT_PREFERRED_KEYWORD_WEIGHT
        )
        return base * (1.0 + 0.25 * (self.occurrences - 1))


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """The result of matching a CV against a job description's keywords.

    Attributes:
        matched: Keywords the CV evidences.
        missing: Keywords it does not.
        score: Weighted coverage from 0 to 100.
    """

    matched: tuple[Keyword, ...] = field(default_factory=tuple)
    missing: tuple[Keyword, ...] = field(default_factory=tuple)
    score: int = 0

    @property
    def missing_required(self) -> tuple[Keyword, ...]:
        """Return the unmatched hard requirements, worst first.

        Returns:
            Missing keywords the posting marked as required.
        """
        return tuple(k for k in self.missing if k.required)


def canonical(term: str) -> str:
    """Reduce a term to the form used for comparison.

    Args:
        term: A raw term.

    Returns:
        The lowercased term with known aliases resolved, so "K8s" and "kubernetes"
        compare equal.
    """
    cleaned = _WHITESPACE.sub(" ", term.strip().casefold())
    # Fold a plural only when the singular is a term we know: "APIs" -> "api", never
    # "aws" -> "aw". Applied to CV and posting alike, so the comparison is symmetric.
    if cleaned.endswith("s") and cleaned not in KNOWN_TERMS:
        singular = cleaned[:-1]
        if singular in KNOWN_TERMS or singular in SKILL_ALIASES:
            cleaned = singular
    return SKILL_ALIASES.get(cleaned, cleaned)


def _clean_token(raw: str) -> str:
    """Normalise a matched token.

    Intra-word punctuation is meaningful in technology names — ``node.js``, ``ci/cd``,
    ``test-driven`` — but the same characters at the end are sentence punctuation.
    Stripping only the trailing ones keeps ``c++`` and ``c#`` intact.

    Args:
        raw: The raw regex match.

    Returns:
        The cleaned, lowercased token.
    """
    return raw.casefold().rstrip("./-")


def tokenise(text: str) -> list[str]:
    """Split text into comparable tokens.

    Args:
        text: Any text.

    Returns:
        Lowercased tokens, punctuation-preserving where it is part of the term.
    """
    return [_clean_token(match.group(0)) for match in _TOKEN.finditer(text)]


def _is_meaningful(token: str) -> bool:
    """Report whether a token is worth matching on.

    Args:
        token: A single token.

    Returns:
        False for stopwords, hiring boilerplate, bare numbers, and very short tokens.
    """
    if token in STOPWORDS or token in JOB_POSTING_BOILERPLATE:
        return False
    # Boilerplate needs its own plural fold: `canonical` only folds known skills, so
    # "experience" was filtered while "experiences" leaked into the gap list.
    if token.endswith("s") and token[:-1] in JOB_POSTING_BOILERPLATE:
        return False
    if len(token) < DEFAULT_KEYWORD_MIN_LENGTH and not token.isupper():
        return token in SKILL_ALIASES or token in KNOWN_TERMS
    return not token.replace(".", "").isdigit()


def _company_tokens(company: str | None) -> frozenset[str]:
    """Terms drawn from the hiring company's own name, to be ignored.

    Almost every posting repeats the company name, and the extractor has no way to know
    it is not a skill — a live sync reported `a.team` and `lemon.io` as hard
    requirements the candidate was missing.

    A name the vocabulary already knows as a skill is **kept**: an Oracle posting asking
    for Oracle experience is stating a real requirement, and dropping it because the
    employer happens to share the name would lose a true signal.

    Args:
        company: The hiring company's name, when the source gives one.

    Returns:
        Canonical terms to exclude, empty when there is no name to work from.
    """
    if not company:
        return frozenset()
    return frozenset(
        term
        for token in tokenise(company)
        if (term := canonical(token)) not in KNOWN_TERMS
    )


def _phrase_is_prose(phrase: str) -> bool:
    """Report whether a multi-word candidate is recruiting prose rather than a concept.

    The head noun decides it: "ai engineers" and "software engineers" are ways of saying
    "people", while "machine learning" and "data engineering" name things. Known phrases
    are checked before this, so "data engineering" is never reached despite its head.

    Args:
        phrase: A candidate phrase.

    Returns:
        True when the last word is hiring boilerplate.
    """
    head = phrase.rsplit(" ", 1)[-1]
    return head in JOB_POSTING_BOILERPLATE or (
        head.endswith("s") and head[:-1] in JOB_POSTING_BOILERPLATE
    )


def _phrases(tokens: Sequence[str], max_words: int) -> list[str]:
    """Generate candidate single- and multi-word terms.

    Multi-word phrases matter because "machine learning" and "continuous integration"
    are single concepts that neither word captures alone.

    Args:
        tokens: The token sequence.
        max_words: Longest phrase to consider.

    Returns:
        Candidate terms, longest first so that a phrase is preferred over its parts.
    """
    candidates: list[str] = []
    for size in range(max_words, 0, -1):
        for index in range(len(tokens) - size + 1):
            window = tokens[index : index + size]
            if size == 1:
                if _is_meaningful(window[0]):
                    candidates.append(window[0])
            elif all(token not in STOPWORDS for token in window):
                candidates.append(" ".join(window))
    return candidates


def _requirement_spans(text: str) -> list[tuple[int, bool]]:
    """Locate the points where a posting switches between required and preferred.

    Args:
        text: The lowercased job description.

    Returns:
        ``(offset, required)`` pairs in document order.
    """
    marks: list[tuple[int, bool]] = []
    for marker in REQUIRED_MARKERS:
        marks.extend((m.start(), True) for m in re.finditer(re.escape(marker), text))
    for marker in PREFERRED_MARKERS:
        marks.extend((m.start(), False) for m in re.finditer(re.escape(marker), text))
    return sorted(marks)


def _is_required_at(marks: Sequence[tuple[int, bool]], offset: int) -> bool:
    """Decide whether text at an offset sits under a required or preferred heading.

    Args:
        marks: Sorted requirement markers.
        offset: Character offset into the description.

    Returns:
        True when the nearest preceding marker introduced hard requirements. Text
        before any marker is treated as required, since a posting that never says
        "preferred" is stating requirements.
    """
    required = True
    for position, is_required in marks:
        if position > offset:
            break
        required = is_required
    return required


def extract_keywords(
    job_description: str,
    *,
    max_phrase_words: int = DEFAULT_KEYWORD_MAX_PHRASE_WORDS,
    company: str | None = None,
) -> tuple[Keyword, ...]:
    """Extract the terms a job description is asking for.

    Args:
        job_description: The posting text.
        max_phrase_words: Longest multi-word term to consider.
        company: The hiring company, so its own name is not reported as a skill.

    Returns:
        Unique keywords, required ones first, then by how often they appeared.
    """
    lowered = job_description.casefold()
    marks = _requirement_spans(lowered)
    excluded = _company_tokens(company)

    counts: dict[str, int] = {}
    required_flags: dict[str, bool] = {}

    for match in _TOKEN.finditer(job_description):
        token = _clean_token(match.group(0))
        if not _is_meaningful(token) or token in excluded:
            continue
        term = canonical(token)
        if term in excluded:
            continue
        counts[term] = counts.get(term, 0) + 1
        # A term is required if it is ever stated as one.
        required_flags[term] = required_flags.get(term, False) or _is_required_at(
            marks, match.start()
        )

    tokens = tokenise(job_description)
    phrase_counts: dict[str, int] = {}
    for phrase in _phrases(tokens, max_phrase_words):
        if " " in phrase:
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

    for phrase, occurrences in phrase_counts.items():
        term = canonical(phrase)
        # An arbitrary run of words is usually prose. A phrase counts only if it is a
        # known concept or the posting repeats it.
        if term not in KNOWN_PHRASES and (occurrences < 2 or _phrase_is_prose(term)):
            continue
        if term in excluded or any(word in excluded for word in term.split()):
            continue
        position = lowered.find(phrase)
        if position == -1:
            continue
        counts[term] = counts.get(term, 0) + occurrences
        required_flags[term] = required_flags.get(term, False) or _is_required_at(
            marks, position
        )

    # A phrase subsumes its parts: "full stack" must not also report "full". The
    # token pass cannot know this — the phrase is only recognised afterwards.
    for term in [t for t in counts if " " in t]:
        for component in term.split():
            counts.pop(component, None)
            required_flags.pop(component, None)

    keywords = [
        Keyword(term=term, required=required_flags[term], occurrences=count)
        for term, count in counts.items()
    ]
    keywords.sort(key=lambda k: (not k.required, -k.occurrences, k.term))
    return tuple(keywords)


def _evidences(cv_terms: set[str], keyword: Keyword) -> bool:
    """Report whether a CV evidences a keyword.

    A multi-word term counts as present only if the whole phrase appears: a CV
    mentioning "learning" has not demonstrated "machine learning".

    Args:
        cv_terms: Canonical terms drawn from the CV.
        keyword: The term to look for.

    Returns:
        True if the CV shows the term.
    """
    return keyword.term in cv_terms


def cv_terms(
    cv_text: str, *, max_phrase_words: int = DEFAULT_KEYWORD_MAX_PHRASE_WORDS
) -> set[str]:
    """Reduce a CV to the set of canonical terms it evidences.

    Args:
        cv_text: The extracted CV text.
        max_phrase_words: Longest multi-word term to index.

    Returns:
        Canonical terms present in the CV.
    """
    tokens = tokenise(cv_text)
    terms = {canonical(token) for token in tokens if _is_meaningful(token)}
    terms.update(canonical(phrase) for phrase in _phrases(tokens, max_phrase_words))
    return terms


def coverage(cv_text: str, keywords: Iterable[Keyword]) -> CoverageReport:
    """Score how well a CV covers a job description's keywords.

    Args:
        cv_text: The extracted CV text.
        keywords: Keywords from the job description.

    Returns:
        The matched and missing terms with a weighted score out of 100. An empty
        keyword list scores 100 — there is nothing to fail to cover.
    """
    terms = cv_terms(cv_text)
    matched: list[Keyword] = []
    missing: list[Keyword] = []

    for keyword in keywords:
        (matched if _evidences(terms, keyword) else missing).append(keyword)

    total = sum(k.weight for k in matched) + sum(k.weight for k in missing)
    score = 100 if total == 0 else round(sum(k.weight for k in matched) / total * 100)

    return CoverageReport(
        matched=tuple(matched), missing=tuple(missing), score=int(score)
    )


def analyse(
    cv_text: str, job_description: str, *, company: str | None = None
) -> CoverageReport:
    """Run the full keyword comparison for a CV against a posting.

    Args:
        cv_text: The extracted CV text.
        job_description: The posting text.
        company: The hiring company, so its own name is not scored as a missing skill.

    Returns:
        The coverage report.
    """
    return coverage(cv_text, extract_keywords(job_description, company=company))
