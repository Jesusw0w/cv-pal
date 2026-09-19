from cv_pal.analysis.evidence import (
    ExperienceFacts,
    SkillFacts,
    suggest_evidence,
)

BILLING = ExperienceFacts(
    id=1,
    title="Backend Engineer",
    organisation="Acme",
    description="Built the billing service in Python on PostgreSQL, deployed with K8s.",
)
SUPPORT = ExperienceFacts(
    id=2,
    title="Support Engineer",
    organisation="Northwind",
    description="Handled escalations. Wrote runbooks and did machine learning work.",
)


def skill(skill_id: int, name: str, canonical_name: str) -> SkillFacts:
    """A skill as the profile stores it."""
    return SkillFacts(id=skill_id, name=name, canonical_name=canonical_name)


def test_a_role_that_names_a_skill_is_proposed_as_its_evidence() -> None:
    """The citation is usually already sitting in prose the user wrote."""
    found = suggest_evidence(
        (skill(10, "Python", "python"),), (BILLING, SUPPORT), already_cited={}
    )

    assert len(found) == 1
    assert found[0].skill_id == 10
    assert found[0].experience_ids == (1,)


def test_an_alias_in_the_description_still_counts() -> None:
    """A description saying K8s evidences a skill stored as Kubernetes.

    The canonical form is what the whole analysis compares on; if it did not reach here
    the suggestions would disagree with the coverage report about what a term means.
    """
    found = suggest_evidence(
        (skill(11, "Kubernetes", "kubernetes"),), (BILLING,), already_cited={}
    )

    assert found[0].experience_ids == (1,)


def test_a_short_skill_name_does_not_match_a_word_that_contains_it() -> None:
    """Substring matching would evidence "Go" from "Handled escalations".

    This is the failure that matters: a plausible-looking wrong suggestion gets
    confirmed, and an unbacked claim reaches a CV.
    """
    found = suggest_evidence(
        (skill(12, "Go", "go"),), (BILLING, SUPPORT), already_cited={}
    )

    assert found == ()


def test_a_multi_word_skill_needs_the_whole_phrase() -> None:
    """A two-word skill is not evidenced by a role that says each word separately."""
    scattered = ExperienceFacts(
        id=3,
        title="Operator",
        organisation="Acme",
        description="Ran the machine room. Kept learning on the job.",
    )

    assert (
        suggest_evidence(
            (skill(13, "Machine Learning", "machine learning"),),
            (scattered,),
            already_cited={},
        )
        == ()
    )
    assert suggest_evidence(
        (skill(13, "Machine Learning", "machine learning"),),
        (SUPPORT,),
        already_cited={},
    )[0].experience_ids == (2,)


def test_roles_already_cited_are_not_proposed_again() -> None:
    """A suggestion has to be something to confirm, not something already true."""
    found = suggest_evidence(
        (skill(10, "Python", "python"),),
        (BILLING,),
        already_cited={10: frozenset({1})},
    )

    assert found == ()


def test_the_title_evidences_a_skill_too() -> None:
    """Not every role has a description, and the title is evidence the user wrote."""
    undescribed = ExperienceFacts(
        id=4, title="Python Engineer", organisation="Acme", description=None
    )

    found = suggest_evidence(
        (skill(10, "Python", "python"),), (undescribed,), already_cited={}
    )

    assert found[0].experience_ids == (4,)
