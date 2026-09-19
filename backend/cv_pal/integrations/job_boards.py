"""Reading job postings from sanctioned ATS boards and job feeds.

Only **Tier A** sources live here: boards publishing a documented, unauthenticated
JSON endpoint for their own listings. Greenhouse and Lever both do, which is why they
are first — no key, no scraping, no terms to breach, no account of the user's at risk.

Greenhouse and Lever answer *"what is open at this company"*, which means you have to
name the company first. **Remotive answers "what remote roles are open at all"**, and
is here because that is the question a remote job search actually starts from. It is a
feed rather than a company board, so `identifier` holds a category slug instead of a
company slug — see `RemotiveBoard`.

**There is deliberately no general URL fetcher.** Two reasons, and the second is the one
that matters:

1. Scraping an arbitrary careers page means parsing whatever HTML it happens to ship,
   and it breaks silently the week the site is restyled.
2. Fetching a URL the user supplies, from the server, is a server-side request forgery
   primitive: on a self-hosted install the API can usually reach the router, the
   metadata endpoint of whatever cloud it runs on, and every other service on the host.
   A "paste the link" convenience is not worth handing that to anyone who can register.

So a link is accepted only when it is recognisably a Greenhouse or Lever posting, and it
is resolved through that board's own API rather than by fetching the page. Anything else
is refused with a message pointing at paste, which always works and cannot break.
"""

import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from cv_pal.constants import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_MAX_POSTING_LENGTH,
    DEFAULT_REMOTIVE_FEED_URL,
    EmploymentType,
    JobSource,
)
from cv_pal.exceptions import JobBoardError

# Greenhouse: boards.greenhouse.io/<board>/jobs/<id>, and the newer job-boards.* host.
_GREENHOUSE_URL = re.compile(
    r"https?://(?:boards|job-boards)\.greenhouse\.io/(?P<board>[\w-]+)/jobs/(?P<id>\d+)",
    re.IGNORECASE,
)
# Lever: jobs.lever.co/<company>/<uuid>
_LEVER_URL = re.compile(
    r"https?://jobs\.lever\.co/(?P<company>[\w-]+)/(?P<id>[\w-]+)",
    re.IGNORECASE,
)
# Remotive: remotive.com/remote-jobs/<category-slug>/<title-slug>-<id>. The slug is
# the categories endpoint's own vocabulary, so filtering needs no second request.
_REMOTIVE_URL = re.compile(
    r"https?://remotive\.com/remote-jobs/(?P<category>[\w-]+)/[\w-]*?(?P<id>\d+)/?$",
    re.IGNORECASE,
)

_TAGS = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True, slots=True)
class BoardPosting:
    """A posting as a board returned it, before it becomes a stored record."""

    source: JobSource
    external_id: str
    url: str
    title: str
    company: str | None
    location: str | None
    description: str
    # Greenhouse and Lever do not expose the contract as a field, and inferring it
    # from prose would be a guess presented as a fact.
    employment_type: EmploymentType | None = None


class JobBoard(Protocol):
    """One ATS board CV Pal can read from."""

    source: JobSource

    async def list_board(
        self, client: httpx.AsyncClient, identifier: str
    ) -> list[BoardPosting]:
        """Read every currently open posting on one company's board."""
        ...

    def matches(self, url: str) -> bool:
        """Report whether this board recognises the URL."""
        ...

    async def fetch(self, client: httpx.AsyncClient, url: str) -> BoardPosting:
        """Read the posting the URL points at."""
        ...


def strip_html(raw: str) -> str:
    """Reduce a board's HTML description to readable text.

    Boards return descriptions as HTML fragments. The analysis only ever reads words, so
    the tags are noise — and keeping them would corrupt the keyword extraction, which
    would happily report ``div`` and ``strong`` as skills a posting requires.

    Args:
        raw: The HTML fragment.

    Returns:
        Plain text, with paragraph breaks preserved and runs of blank lines collapsed.
    """
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|div|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = _TAGS.sub(" ", text)
    for entity, char in (
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
        ("&nbsp;", " "),
    ):
        text = text.replace(entity, char)
    text = _WHITESPACE.sub(" ", text)
    return _BLANK_LINES.sub("\n\n", text).strip()[:DEFAULT_MAX_POSTING_LENGTH]


class GreenhouseBoard:
    """Greenhouse's public board API. No credential — the data is already public."""

    source = JobSource.GREENHOUSE

    def matches(self, url: str) -> bool:
        """Report whether the URL is a Greenhouse posting.

        Args:
            url: A candidate URL.

        Returns:
            True when it is.
        """
        return _GREENHOUSE_URL.search(url) is not None

    async def fetch(self, client: httpx.AsyncClient, url: str) -> BoardPosting:
        """Read a Greenhouse posting.

        Args:
            client: The HTTP client to use.
            url: The posting URL.

        Returns:
            The posting.

        Raises:
            JobBoardError: If the URL is not a Greenhouse posting, or the board does not
                answer with a usable document.
        """
        match = _GREENHOUSE_URL.search(url)
        if match is None:
            raise JobBoardError
        board, job_id = match.group("board"), match.group("id")

        payload = await _get_json(
            client,
            f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}",
        )
        return BoardPosting(
            source=JobSource.GREENHOUSE,
            external_id=job_id,
            url=str(payload.get("absolute_url") or url),
            title=str(payload.get("title") or "Untitled role"),
            company=board.replace("-", " ").title(),
            location=_nested_str(payload.get("location"), "name"),
            description=strip_html(str(payload.get("content") or "")),
        )

    async def list_board(
        self, client: httpx.AsyncClient, identifier: str
    ) -> list[BoardPosting]:
        """Read every open posting on one Greenhouse board.

        Args:
            client: The HTTP client to use.
            identifier: The board token — the ``acme`` in ``boards.greenhouse.io/acme``.

        Returns:
            The postings. An empty board is a valid answer, not an error.

        Raises:
            JobBoardError: If the board could not be read.
        """
        payload = await _get_json(
            client,
            f"https://boards-api.greenhouse.io/v1/boards/{identifier}/jobs?content=true",
        )
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise JobBoardError

        found: list[BoardPosting] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            if not job_id:
                continue
            found.append(
                BoardPosting(
                    source=JobSource.GREENHOUSE,
                    external_id=job_id,
                    url=str(job.get("absolute_url") or ""),
                    title=str(job.get("title") or "Untitled role"),
                    company=identifier.replace("-", " ").title(),
                    location=_nested_str(job.get("location"), "name"),
                    description=strip_html(str(job.get("content") or "")),
                )
            )
        return found


class LeverBoard:
    """Lever's public postings API."""

    source = JobSource.LEVER

    def matches(self, url: str) -> bool:
        """Report whether the URL is a Lever posting.

        Args:
            url: A candidate URL.

        Returns:
            True when it is.
        """
        return _LEVER_URL.search(url) is not None

    async def fetch(self, client: httpx.AsyncClient, url: str) -> BoardPosting:
        """Read a Lever posting.

        Args:
            client: The HTTP client to use.
            url: The posting URL.

        Returns:
            The posting.

        Raises:
            JobBoardError: If the URL is not a Lever posting, or the board does not
                answer with a usable document.
        """
        match = _LEVER_URL.search(url)
        if match is None:
            raise JobBoardError
        company, job_id = match.group("company"), match.group("id")

        payload = await _get_json(
            client, f"https://api.lever.co/v0/postings/{company}/{job_id}"
        )

        return BoardPosting(
            source=JobSource.LEVER,
            external_id=job_id,
            url=str(payload.get("hostedUrl") or url),
            title=str(payload.get("text") or "Untitled role"),
            company=company.replace("-", " ").title(),
            location=_nested_str(payload.get("categories"), "location"),
            description=strip_html(
                str(payload.get("descriptionPlain") or payload.get("description") or "")
            ),
        )

    async def list_board(
        self, client: httpx.AsyncClient, identifier: str
    ) -> list[BoardPosting]:
        """Read every open posting on one Lever board.

        Args:
            client: The HTTP client to use.
            identifier: The company slug — the ``acme`` in ``jobs.lever.co/acme``.

        Returns:
            The postings.

        Raises:
            JobBoardError: If the board could not be read.
        """
        payload = await _get_json_list(
            client, f"https://api.lever.co/v0/postings/{identifier}?mode=json"
        )

        found: list[BoardPosting] = []
        for job in payload:
            if not isinstance(job, dict):
                continue
            job_id = str(job.get("id") or "")
            if not job_id:
                continue
            found.append(
                BoardPosting(
                    source=JobSource.LEVER,
                    external_id=job_id,
                    url=str(job.get("hostedUrl") or ""),
                    title=str(job.get("text") or "Untitled role"),
                    company=identifier.replace("-", " ").title(),
                    location=_nested_str(job.get("categories"), "location"),
                    description=strip_html(
                        str(job.get("descriptionPlain") or job.get("description") or "")
                    ),
                )
            )
        return found


class RemotiveBoard:
    """Remotive's public feed of remote-only roles.

    The other two boards answer *"what is open at this company"*, so you must already
    know the company. This one answers *"what remote roles are open at all"*, which is
    where a remote search actually starts — so `identifier` holds one of Remotive's
    **category slugs** (`software-development`, `devops`, `data`, …) rather than a
    company slug.

    Two properties of the feed shape everything below:

    - **Its query parameters do not work.** `search`, `category` and `limit` are
      accepted and then ignored — verified 2026-08-08, every combination returns the
      identical set. So the whole feed is fetched once and filtered here. Sending the
      parameters anyway would be cargo cult, and it would hide the day they start
      working behind an apparently-correct call.
    - **It is small, recent and rotating** — tens of roles, delayed 24 hours by their
      own terms. It is a stream to watch, not an archive to search. A category with
      nothing in it today is a normal answer, not a failure, and the same sync run
      tomorrow will find different roles.

    Attribution is a requirement here rather than a courtesy: Remotive's terms ask for
    a link back to their URL and a mention of Remotive as the source. Both fall out of
    storing their `url` as `source_url`, which the interface links and labels — so the
    obligation is met by the normal path and cannot be forgotten. Their terms also ask
    for no more than a few calls a day, which one manual sync per watched category is
    comfortably inside.
    """

    source = JobSource.REMOTIVE

    def matches(self, url: str) -> bool:
        """Report whether the URL is a Remotive posting.

        Args:
            url: A candidate URL.

        Returns:
            True when it is.
        """
        return _REMOTIVE_URL.search(url) is not None

    async def fetch(self, client: httpx.AsyncClient, url: str) -> BoardPosting:
        """Read one Remotive posting.

        There is no per-posting endpoint, so this reads the feed and picks the entry
        out of it. A posting that has aged out of the feed is therefore unreachable,
        and is reported as such — which routes the user to paste, the one path that
        cannot fail.

        Args:
            client: The HTTP client to use.
            url: The posting URL.

        Returns:
            The posting.

        Raises:
            JobBoardError: If the URL is not a Remotive posting, the feed could not be
                read, or the posting is no longer in it.
        """
        match = _REMOTIVE_URL.search(url)
        if match is None:
            raise JobBoardError
        wanted = match.group("id")

        for posting in await self._feed(client):
            if posting.external_id == wanted:
                return posting
        raise JobBoardError

    async def list_board(
        self, client: httpx.AsyncClient, identifier: str
    ) -> list[BoardPosting]:
        """Read every current remote posting in one Remotive category.

        Args:
            client: The HTTP client to use.
            identifier: A Remotive category slug — the ``devops`` in
                ``remotive.com/remote-jobs/devops/…``.

        Returns:
            The postings in that category. Empty is a valid answer: the feed holds only
            what is currently open, and an unknown slug is indistinguishable from a
            category that happens to be quiet today.

        Raises:
            JobBoardError: If the feed could not be read.
        """
        wanted = identifier.casefold()
        return [
            posting
            for posting in await self._feed(client)
            if _remotive_category(posting.url) == wanted
        ]

    async def _feed(self, client: httpx.AsyncClient) -> list[BoardPosting]:
        """Read and parse the whole feed.

        Returns:
            Every posting the feed currently carries, unfiltered.

        Raises:
            JobBoardError: If the feed could not be read or is not shaped as expected.
        """
        payload = await _get_json(client, DEFAULT_REMOTIVE_FEED_URL)
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise JobBoardError

        found: list[BoardPosting] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            posting = _remotive_posting(job)
            if posting is not None:
                found.append(posting)
        return found


BOARDS: tuple[JobBoard, ...] = (GreenhouseBoard(), LeverBoard(), RemotiveBoard())


def board_by_source(source: JobSource | str) -> JobBoard | None:
    """Return the board implementation for a stored connection.

    Compares by value rather than identity, and accepts a plain string: the column is a
    `String`, so a source read back from the database is `"greenhouse"` rather than the
    enum member, and an identity check silently finds nothing.

    Args:
        source: The source recorded against a saved connection.

    Returns:
        The board, or None when the source has no board behind it —
        `JobSource.MANUAL` is a paste, not a place to fetch from.
    """
    return next((board for board in BOARDS if board.source == source), None)


def board_for(url: str) -> JobBoard | None:
    """Return the board that recognises a URL, or None.

    Args:
        url: A candidate URL.

    Returns:
        The matching board, or None when no sanctioned board claims it — in which case
        the caller must ask the user to paste instead. There is no general fetcher.
    """
    return next((board for board in BOARDS if board.matches(url)), None)


def _remotive_category(url: str) -> str | None:
    """Read the category slug out of a Remotive posting URL.

    The slug is taken from the URL rather than from the `category` field because the
    field carries the display *name* (``Data and Analytics``) while the categories
    endpoint publishes *slugs* (``data``). The URL already contains the slug, so
    reading it there avoids a second request for a name-to-slug map that would then
    need to stay in step with theirs.

    Args:
        url: The posting URL.

    Returns:
        The slug, casefolded, or None when the URL is not shaped as expected.
    """
    match = _REMOTIVE_URL.search(url)
    return match.group("category").casefold() if match else None


def _remotive_posting(job: dict[str, object]) -> BoardPosting | None:
    """Turn one feed entry into a posting.

    Args:
        job: One object from the feed's ``jobs`` array.

    Returns:
        The posting, or None when it carries no id or no URL — without a URL the
        attribution Remotive's terms require cannot be shown, so the entry is dropped
        rather than stored unattributed.
    """
    job_id = str(job.get("id") or "").strip()
    url = str(job.get("url") or "").strip()
    if not job_id or not url:
        return None

    company = str(job.get("company_name") or "").strip()
    where = str(job.get("candidate_required_location") or "").strip()

    return BoardPosting(
        source=JobSource.REMOTIVE,
        external_id=job_id,
        url=url,
        title=str(job.get("title") or "Untitled role").strip(),
        company=company or None,
        # The feed is remote-only by premise but does not always say so, and
        # `detect_regimes` reads the location to confirm a non-negotiable.
        location=f"Remote · {where}" if where else "Remote",
        description=strip_html(str(job.get("description") or "")),
        employment_type=_employment_type(job.get("job_type")),
    )


def _employment_type(value: object) -> EmploymentType | None:
    """Read the contract a posting offers, tolerating anything unexpected.

    Args:
        value: The feed's ``job_type``.

    Returns:
        The contract type, or None. The feed emits an empty string for postings that do
        not state one, and an unrecognised value gets the same answer as an absent one:
        a contract type invented from a string we do not know is worse than no answer.
    """
    if not isinstance(value, str):
        return None
    try:
        return EmploymentType(value.strip().casefold())
    except ValueError:
        return None


def _nested_str(value: object, key: str) -> str | None:
    """Read a string out of a nested board object, tolerating a missing one.

    Boards vary in whether an absent field is omitted, null, or an empty object, and a
    location is never worth failing an import over.

    Args:
        value: The nested value the board returned.
        key: The field to read.

    Returns:
        The string, or None.
    """
    if isinstance(value, dict):
        inner = value.get(key)
        if isinstance(inner, str) and inner.strip():
            return inner
    return None


async def _get_json_list(client: httpx.AsyncClient, url: str) -> list[object]:
    """GET a board API that answers with a bare JSON array.

    Args:
        client: The HTTP client to use.
        url: The board API URL, built here from a stored identifier.

    Returns:
        The decoded array.

    Raises:
        JobBoardError: On any transport, status or decoding failure.
    """
    try:
        response = await client.get(
            url,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise JobBoardError from exc

    if not isinstance(payload, list):
        raise JobBoardError
    return payload


async def _get_json(client: httpx.AsyncClient, url: str) -> dict[str, object]:
    """GET a board's API and return the decoded document.

    Args:
        client: The HTTP client to use.
        url: The board API URL — constructed here from a matched pattern, never taken
            from the user directly.

    Returns:
        The decoded JSON object.

    Raises:
        JobBoardError: On any transport, status or decoding failure. The caller cannot
            do anything different for each, and the user's next step is the same: paste.
    """
    try:
        response = await client.get(
            url,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise JobBoardError from exc

    if not isinstance(payload, dict):
        raise JobBoardError
    return payload
