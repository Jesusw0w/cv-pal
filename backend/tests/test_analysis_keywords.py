from cv_pal.analysis.keywords import (
    analyse,
    canonical,
    coverage,
    cv_terms,
    extract_keywords,
)

JOB_DESCRIPTION = """
Senior Backend Engineer

Requirements:
- Strong Python experience
- Experience with PostgreSQL and Docker
- Familiarity with Kubernetes

Nice to have:
- Terraform
- GraphQL
"""

CV_TEXT = """
Jane Doe — Backend Engineer

Experience
- Built services in Python, deployed with Docker
- Designed schemas on PostgreSQL
"""


def test_canonical_resolves_aliases() -> None:
    """Different spellings of a skill compare equal."""
    assert canonical("K8s") == canonical("Kubernetes")
    assert canonical("JS") == "javascript"
    assert canonical("  Postgres ") == "postgresql"


def test_extracts_terms_from_a_posting() -> None:
    """The obvious technologies are picked up."""
    terms = {k.term for k in extract_keywords(JOB_DESCRIPTION)}

    assert "python" in terms
    assert "postgresql" in terms
    assert "kubernetes" in terms


def test_distinguishes_required_from_preferred() -> None:
    """Terms under a 'nice to have' heading are not treated as requirements."""
    keywords = {k.term: k for k in extract_keywords(JOB_DESCRIPTION)}

    assert keywords["python"].required
    assert not keywords["terraform"].required


def test_required_terms_sort_first() -> None:
    """The ordering puts hard requirements at the top."""
    keywords = extract_keywords(JOB_DESCRIPTION)

    first_optional = next(i for i, k in enumerate(keywords) if not k.required)
    assert all(k.required for k in keywords[:first_optional])


def test_stopwords_and_filler_are_dropped() -> None:
    """Job-advert filler does not become a keyword."""
    terms = {k.term for k in extract_keywords(JOB_DESCRIPTION)}

    for noise in ("the", "with", "experience", "strong", "requirements"):
        assert noise not in terms


def test_required_terms_weigh_more_than_preferred() -> None:
    """Missing a requirement costs more than missing a bonus."""
    keywords = {k.term: k for k in extract_keywords(JOB_DESCRIPTION)}

    assert keywords["python"].weight > keywords["terraform"].weight


def test_repetition_increases_weight() -> None:
    """A term the posting repeats matters more than one mentioned once."""
    keywords = {k.term: k for k in extract_keywords("Python. Python. Python. Docker.")}

    assert keywords["python"].weight > keywords["docker"].weight


def test_coverage_separates_matched_from_missing() -> None:
    """Terms the CV evidences are matched; the rest are gaps."""
    report = analyse(CV_TEXT, JOB_DESCRIPTION)

    matched = {k.term for k in report.matched}
    missing = {k.term for k in report.missing}

    assert {"python", "docker", "postgresql"} <= matched
    assert "kubernetes" in missing


def test_missing_required_isolates_the_hard_gaps() -> None:
    """Unmet requirements can be separated from unmet bonuses."""
    report = analyse(CV_TEXT, JOB_DESCRIPTION)

    missing_required = {k.term for k in report.missing_required}

    assert "kubernetes" in missing_required
    assert "terraform" not in missing_required


def test_alias_in_the_cv_matches_the_canonical_term_in_the_posting() -> None:
    """Writing 'K8s' on a CV satisfies a posting asking for Kubernetes."""
    report = analyse(
        "Ran workloads on K8s in production since 2020", "Requires Kubernetes"
    )

    assert {k.term for k in report.matched} == {"kubernetes"}


def test_score_is_zero_when_nothing_matches() -> None:
    """A CV sharing no terms with the posting scores zero."""
    report = analyse("Pastry chef. Baked bread since 2019.", JOB_DESCRIPTION)

    assert report.score == 0


def test_score_is_one_hundred_when_everything_matches() -> None:
    """Full coverage scores full marks.

    The posting asks for the role words as well as the technologies — a CV listing only
    tools genuinely has not covered "Senior Backend Engineer".
    """
    everything = " ".join(k.term for k in extract_keywords(JOB_DESCRIPTION))

    report = analyse(everything, JOB_DESCRIPTION)

    assert report.score == 100
    assert report.missing == ()


def test_empty_posting_scores_full_marks() -> None:
    """There is nothing to fail to cover, so the score is not a division by zero."""
    report = coverage(CV_TEXT, [])

    assert report.score == 100
    assert report.matched == ()


def test_partial_coverage_scores_between() -> None:
    """A CV covering some requirements lands strictly between the extremes."""
    report = analyse(CV_TEXT, JOB_DESCRIPTION)

    assert 0 < report.score < 100


def test_multi_word_terms_need_the_whole_phrase() -> None:
    """Mentioning 'learning' does not demonstrate 'machine learning'."""
    terms = cv_terms(
        "Continuous learning is important to me. I have used Python since 2019."
    )

    assert "machine learning" not in terms


def test_analysis_is_deterministic() -> None:
    """The same inputs always produce the same report."""
    first = analyse(CV_TEXT, JOB_DESCRIPTION)
    second = analyse(CV_TEXT, JOB_DESCRIPTION)

    assert first == second


def test_hiring_boilerplate_is_not_a_skill() -> None:
    """A posting's own recruiting prose is not a requirement the CV is missing.

    Found by running the analysis against a real CV: the first report listed
    "hiring" and "engineer" among the missing required skills, which makes the
    whole score untrustworthy.
    """
    terms = {
        k.term
        for k in extract_keywords(
            "We are hiring an engineer. Requirements: strong experience with Python. "
            "The successful candidate will join a team with excellent skills."
        )
    }

    assert "python" in terms
    for boilerplate in ("hiring", "engineer", "experience", "candidate", "team"):
        assert boilerplate not in terms


def test_a_phrase_subsumes_its_component_words() -> None:
    """A known phrase is not also reported as its component words.

    The token pass runs before phrases are recognised, so without an explicit
    subsumption step every known phrase leaks its own parts as separate keywords.
    """
    terms = {
        k.term
        for k in extract_keywords(
            "Requirements: full stack development and machine learning."
        )
    }

    assert "full stack" in terms
    assert "machine learning" in terms
    for component in ("full", "stack", "machine", "learning"):
        assert component not in terms


def test_plurals_fold_only_when_the_singular_is_known() -> None:
    """Plural REST APIs matches rest api, while aws is never mangled into aw."""
    assert canonical("REST APIs") == "rest api"
    # aws resolves through the alias map, which would be unreachable if the
    # trailing "s" had been stripped first.
    assert canonical("AWS") == "amazon web services"


REAL_SHAPED_POSTING = """
A.Team is a network of senior engineers. We need people who love solving hard problems.

Requirements:
- Strong commercial experience with Go, Kubernetes and PostgreSQL
- The best engineers in the industry, delivering real business value for clients

Our AI engineers build AI systems for customers across the world every day.
"""


def test_short_known_terms_survive_the_length_filter() -> None:
    """`go` is two characters and was silently unextractable.

    It is a value in the alias map (`golang` -> `go`), never a key, and the length
    filter only consulted the keys. A tool for software roles could not see Go at all.
    """
    terms = {k.term for k in extract_keywords(REAL_SHAPED_POSTING)}

    assert "go" in terms


def test_the_hiring_company_is_not_reported_as_a_missing_skill() -> None:
    """A live sync reported `a.team` as a hard requirement the candidate lacked."""
    with_company = {
        k.term for k in extract_keywords(REAL_SHAPED_POSTING, company="A.Team")
    }
    without = {k.term for k in extract_keywords(REAL_SHAPED_POSTING)}

    assert "a.team" in without
    assert "a.team" not in with_company


def test_recruiting_prose_is_not_reported_as_a_requirement() -> None:
    """A gap list is meant to be acted on.

    Every term here was returned as a missing hard requirement by a live sync. None of
    them is something a candidate could go and learn.
    """
    terms = {k.term for k in extract_keywords(REAL_SHAPED_POSTING, company="A.Team")}

    for noise in (
        "best",
        "business",
        "client",
        "commercial",
        "customer",
        "day",
        "industry",
        "people",
        "problem",
        "senior",
        "value",
        "world",
        # Phrase noise: the head noun is a way of saying "people", not a concept.
        "ai engineers",
    ):
        assert noise not in terms, f"{noise!r} is prose, not a requirement"

    # The real requirements are still there — the filter must not have eaten the signal.
    assert {"go", "kubernetes", "postgresql"} <= terms
