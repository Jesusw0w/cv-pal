"""How much a document repeats the user's own previous ones.

From PLANNING → *"Will an ATS flag this as AI?" — the honest version*. That section
rejects AI-text detection outright — it is unobservable, the detectors over-flag
non-native speakers, and a number the product cannot defend has no place in a product
whose position is that its numbers are defensible. It replaces the question with
measurable ones, and this is the strongest of them:

> **Self-similarity.** Shingled similarity of this letter against the user's own recent
> ones. **This is the strongest signal available and it is available to nobody else:**
> only a tool holding the whole application history can see that the last ten letters
> were 92% identical. That is spray-and-pray by definition, whatever produced the text.

Two properties worth being explicit about, because they are what make this fair:

- **It measures the user against themselves, never against a corpus.** There is no
  model of what "human writing" looks like, so there is nothing here to be wrong about
  someone's style, first language or plainness.
- **A high score is not an accusation.** It is a description: *these letters are nearly
  the same document*. The user may have good reason. The check warns, and never blocks
  — see the gate's table.

w-shingling with Jaccard similarity: standard near-duplicate detection, order-sensitive
enough to notice reordered paragraphs, cheap enough to run on every draft, and entirely
explainable — which a vector embedding would not be.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from cv_pal.constants import DEFAULT_SHINGLE_WORDS

_WORD = re.compile(r"[a-z0-9']+")


@dataclass(frozen=True, slots=True)
class SimilarityResult:
    """How close a draft is to the nearest thing the user has written before.

    Attributes:
        score: 0 to 100. Zero when there is nothing to compare against, which is the
            honest answer for a first letter rather than a flattering one.
        closest: Index into the previous documents of the nearest match, or None.
    """

    score: int
    closest: int | None = None


def shingles(text: str, size: int = DEFAULT_SHINGLE_WORDS) -> frozenset[str]:
    """Break text into overlapping runs of words.

    Words rather than characters, and overlapping rather than split, so that inserting
    one sentence shifts a handful of shingles instead of every one after it. That is
    what makes the measure track *how much was rewritten* rather than *where*.

    Args:
        text: The document.
        size: Words per shingle.

    Returns:
        The distinct shingles. A document shorter than one shingle yields a single
        shingle of everything it has, so two short documents still compare.
    """
    words = _WORD.findall(text.casefold())
    if not words:
        return frozenset()
    if len(words) <= size:
        return frozenset({" ".join(words)})
    return frozenset(
        " ".join(words[index : index + size]) for index in range(len(words) - size + 1)
    )


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    """Overlap between two shingle sets.

    Args:
        left: One document's shingles.
        right: The other's.

    Returns:
        0.0 to 1.0. Two empty documents score 0.0 rather than 1.0 — "identical
        emptiness" is not a similarity anyone wants reported.
    """
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def self_similarity(draft: str, previous: Sequence[str]) -> SimilarityResult:
    """Compare a draft against the user's own earlier documents.

    Args:
        draft: The document about to be sent.
        previous: What the user sent before, newest first.

    Returns:
        The closest match and its score.
    """
    if not previous:
        return SimilarityResult(score=0)

    draft_shingles = shingles(draft)
    scores = [jaccard(draft_shingles, shingles(earlier)) for earlier in previous]
    best = max(range(len(scores)), key=lambda index: scores[index])
    return SimilarityResult(score=round(scores[best] * 100), closest=best)


__all__ = ["SimilarityResult", "jaccard", "self_similarity", "shingles"]
