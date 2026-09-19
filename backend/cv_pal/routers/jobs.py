from fastapi import APIRouter, Response, status

from cv_pal.constants import (
    DEFAULT_DOCX_MEDIA_TYPE,
    DEFAULT_PDF_MEDIA_TYPE,
    DEFAULT_SIMILARITY_WARN_THRESHOLD,
)
from cv_pal.dependencies import CurrentUser, DbSession, HttpClient
from cv_pal.generation.docx_export import render_docx
from cv_pal.generation.pdf_export import render_pdf
from cv_pal.schemas import (
    CoverLetterDraftResponse,
    CoverLetterSave,
    FindingResponse,
    GapResponse,
    JobBoardConnectionCreate,
    JobBoardConnectionResponse,
    JobPostingCreate,
    JobPostingImport,
    JobPostingResponse,
    MatchScoreResponse,
    ParseabilityResponse,
    ScoredPostingResponse,
    SubstitutionResponse,
    SurfacedFactResponse,
    SyncResultResponse,
    TailoredCvResponse,
)
from cv_pal.services import cover_letter_service, job_service, tailoring_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[ScoredPostingResponse])
async def list_jobs(
    current_user: CurrentUser, db: DbSession
) -> list[ScoredPostingResponse]:
    """List the user's saved postings, each with its match score.

    Scored on read rather than stored, so a change to the profile or the goals is
    reflected immediately. Scoring is deterministic and cheap — no model is involved —
    which is what makes recomputing it per request reasonable.

    Returns:
        The postings, newest first, each with its score.
    """
    postings = await job_service.list_postings(db, user_id=current_user.id)
    scored = []
    for posting in postings:
        match = await job_service.score(db, user_id=current_user.id, posting=posting)
        scored.append(
            ScoredPostingResponse(
                posting=JobPostingResponse.model_validate(posting),
                match=MatchScoreResponse.model_validate(match),
            )
        )
    return scored


@router.post(
    "/paste", response_model=JobPostingResponse, status_code=status.HTTP_201_CREATED
)
async def paste_job(
    payload: JobPostingCreate, current_user: CurrentUser, db: DbSession
) -> JobPostingResponse:
    """Save a posting the user pasted.

    The fallback that cannot break: no board to be unavailable, no page layout to
    change, no terms to breach. Every other route falls back to this one.

    Args:
        payload: The posting.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The stored posting.
    """
    posting = await job_service.save_pasted(
        db, user_id=current_user.id, payload=payload
    )
    return JobPostingResponse.model_validate(posting)


@router.post(
    "/import-url",
    response_model=JobPostingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_job_url(
    payload: JobPostingImport,
    current_user: CurrentUser,
    db: DbSession,
    client: HttpClient,
) -> JobPostingResponse:
    """Save a posting from a link to a job board CV Pal can read.

    Only Remotive, Greenhouse and Lever links are resolved, and through their own
    published APIs rather than by fetching the page. Anything else is refused with a
    message pointing at paste — see `integrations/job_boards.py` for why there is no
    general fetcher.

    Args:
        payload: The posting URL.
        current_user: The authenticated user.
        db: Async database session.
        client: Shared HTTP client.

    Returns:
        The stored posting.
    """
    posting = await job_service.save_from_url(
        db, user_id=current_user.id, url=payload.url, client=client
    )
    return JobPostingResponse.model_validate(posting)


@router.delete("/{posting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(posting_id: int, current_user: CurrentUser, db: DbSession) -> None:
    """Remove a saved posting.

    Args:
        posting_id: The posting to remove.
        current_user: The authenticated user.
        db: Async database session.
    """
    await job_service.delete_posting(db, user_id=current_user.id, posting_id=posting_id)


@router.post("/{posting_id}/tailor", response_model=TailoredCvResponse)
async def tailor_cv(
    posting_id: int, current_user: CurrentUser, db: DbSession
) -> TailoredCvResponse:
    """Render the career profile as a CV aimed at one saved posting.

    Phase 8's **surface** transform and nothing else: facts already on the profile are
    selected and ordered for this posting. No claim is written that the profile does not
    already make, and anything the posting wants that no role evidences comes back as a
    named gap rather than as text.

    A `POST` despite creating nothing, because it is a computation over a body of facts
    rather than a resource to fetch — and because nothing is stored, so there is no
    identifier a `GET` could address. Deterministic and model-free, so asking twice
    costs nothing and always answers the same.

    Args:
        posting_id: The posting to aim at.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The document, what it surfaced, what it could not, and how it parses.
    """
    tailored, parseability = await tailoring_service.tailor_for_posting(
        db, user=current_user, posting_id=posting_id
    )
    return TailoredCvResponse(
        markdown=tailored.markdown,
        surfaced=[
            SurfacedFactResponse.model_validate(item) for item in tailored.surfaced
        ],
        gaps=[GapResponse.model_validate(gap) for gap in tailored.gaps],
        substitutions=[
            SubstitutionResponse.model_validate(item) for item in tailored.substitutions
        ],
        omitted_unevidenced=list(tailored.omitted_unevidenced),
        parseability=ParseabilityResponse(
            score=parseability.score,
            word_count=parseability.word_count,
            findings=[FindingResponse.model_validate(f) for f in parseability.findings],
            blocking=[FindingResponse.model_validate(f) for f in parseability.blocking],
        ),
    )


@router.post("/{posting_id}/tailor/docx", response_class=Response)
async def tailor_cv_docx(
    posting_id: int, current_user: CurrentUser, db: DbSession
) -> Response:
    """Download the tailored CV as a `.docx`.

    The Markdown is the content; this is the submission format — applicant tracking
    systems ingest `.docx`, not Markdown. Same document, same transforms, rendered
    through `generation.docx_export`.

    Args:
        posting_id: The posting to aim at.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The file, named after the company and role.
    """
    tailored, _ = await tailoring_service.tailor_for_posting(
        db, user=current_user, posting_id=posting_id
    )
    posting = await job_service.get_posting(
        db, user_id=current_user.id, posting_id=posting_id
    )
    filename = tailoring_service.download_name(
        posting.company, posting.title, suffix=".docx"
    )
    return Response(
        content=render_docx(tailored.blocks),
        media_type=DEFAULT_DOCX_MEDIA_TYPE,
        # `filename` is rebuilt from an allowlist in `download_name`, so it cannot
        # carry a quote or a newline into this header.
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{posting_id}/cover-letter", response_model=CoverLetterDraftResponse)
async def draft_cover_letter(
    posting_id: int, current_user: CurrentUser, db: DbSession
) -> CoverLetterDraftResponse:
    """Assemble a cover letter for one posting from facts the profile already states.

    **A draft, not a finished letter**, and the response says so: `needs_writing`
    stays true while the one paragraph nobody can assemble for the user is still a
    placeholder.

    The similarity to the user's own kept letters is returned with it, never
    separately. A deterministic scaffold produces letters that resemble each other —
    exactly what PLANNING's self-similarity check exists to surface — and letting this
    endpoint be used without seeing the number would be the product doing what it says
    it is against.

    Args:
        posting_id: The posting to write to.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The draft, its evidence lines, and how much it repeats the user's other letters.
    """
    draft, similarity, _ = await cover_letter_service.draft_for_posting(
        db, user=current_user, posting_id=posting_id
    )
    return CoverLetterDraftResponse(
        body=draft.body,
        evidence=list(draft.evidence),
        needs_writing=draft.needs_writing,
        similarity=similarity.score,
        similarity_warning=similarity.score >= DEFAULT_SIMILARITY_WARN_THRESHOLD,
    )


@router.put("/{posting_id}/cover-letter", response_model=CoverLetterDraftResponse)
async def save_cover_letter(
    posting_id: int,
    payload: CoverLetterSave,
    current_user: CurrentUser,
    db: DbSession,
) -> CoverLetterDraftResponse:
    """Keep a letter against a posting, replacing any previous one.

    Saving is what puts a letter into the corpus the similarity check reads, so the
    number returned here is computed on **the text being saved** rather than on the
    generated draft — the edited version is the one that would be sent.

    Args:
        posting_id: The posting the letter is for.
        payload: The letter, as edited.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The stored letter with its similarity, and whether the placeholder survives.
    """
    letter, similarity, needs_writing = await cover_letter_service.save_letter(
        db, user=current_user, posting_id=posting_id, body=payload.body
    )
    return CoverLetterDraftResponse(
        body=letter.body,
        evidence=[],
        needs_writing=needs_writing,
        similarity=similarity.score,
        similarity_warning=similarity.score >= DEFAULT_SIMILARITY_WARN_THRESHOLD,
    )


@router.post("/{posting_id}/tailor/pdf", response_class=Response)
async def tailor_cv_pdf(
    posting_id: int, current_user: CurrentUser, db: DbSession
) -> Response:
    """Download the tailored CV as a PDF.

    **Prefer the `.docx` where a portal accepts either**: it is structured data a parser
    reads directly, where a PDF is a page description it has to reconstruct. This exists
    because it is what a human opens, and because some portals accept nothing else.

    Args:
        posting_id: The posting to aim at.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The file, named after the company and role.
    """
    tailored, _ = await tailoring_service.tailor_for_posting(
        db, user=current_user, posting_id=posting_id
    )
    posting = await job_service.get_posting(
        db, user_id=current_user.id, posting_id=posting_id
    )
    filename = tailoring_service.download_name(
        posting.company, posting.title, suffix=".pdf"
    )
    return Response(
        content=render_pdf(tailored.blocks),
        media_type=DEFAULT_PDF_MEDIA_TYPE,
        # Rebuilt from an allowlist in `download_name`, so it cannot carry a quote or a
        # newline into this header.
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/sources", response_model=list[JobBoardConnectionResponse])
async def list_sources(
    current_user: CurrentUser, db: DbSession
) -> list[JobBoardConnectionResponse]:
    """List the company boards this user is watching.

    Returns:
        The connections.
    """
    connections = await job_service.list_connections(db, user_id=current_user.id)
    return [JobBoardConnectionResponse.model_validate(c) for c in connections]


@router.post(
    "/sources",
    response_model=JobBoardConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_source(
    payload: JobBoardConnectionCreate, current_user: CurrentUser, db: DbSession
) -> JobBoardConnectionResponse:
    """Watch a company's Greenhouse or Lever board.

    Args:
        payload: The board to watch.
        current_user: The authenticated user.
        db: Async database session.

    Returns:
        The stored connection.
    """
    connection = await job_service.add_connection(
        db, user_id=current_user.id, payload=payload
    )
    return JobBoardConnectionResponse.model_validate(connection)


@router.post("/sources/sync", response_model=list[SyncResultResponse])
async def sync_all_sources(
    current_user: CurrentUser,
    db: DbSession,
    client: HttpClient,
) -> list[SyncResultResponse]:
    """Fetch every watched source and save whatever is new.

    Declared **before** `/sources/{connection_id}/sync` deliberately: FastAPI matches
    routes in order, and the parameterised path would otherwise claim `sync` as a
    connection id and answer 422.

    This is the one a scheduler calls. Per-connection sync needs the ids up front, so a
    nightly entry meant one command per source; this stays one line as the watch list
    changes. Idempotent by content hash, so running it more often than the sources
    change adds nothing.

    Args:
        current_user: The authenticated user.
        db: Async database session.
        client: Shared HTTP client.

    Returns:
        One result per watched source. An unreachable source reports its error in
        its own result rather than failing the sweep.
    """
    results = await job_service.sync_all_connections(
        db, user_id=current_user.id, client=client
    )
    return [SyncResultResponse.model_validate(result) for result in results]


@router.post("/sources/{connection_id}/sync", response_model=SyncResultResponse)
async def sync_source(
    connection_id: int,
    current_user: CurrentUser,
    db: DbSession,
    client: HttpClient,
) -> SyncResultResponse:
    """Fetch a watched board and save whatever is new.

    **This is the scheduled collection.** It is idempotent by content hash, so calling
    it on a timer re-saves nothing — a board that has not changed adds zero postings.
    That is what lets scheduling be a cron entry or a systemd timer hitting this
    endpoint, rather than a job queue and a Redis dependency in a self-hosted app.

    A board that cannot be read is recorded on the connection rather than raised, so one
    unreachable company does not fail a sweep across all of them.

    Args:
        connection_id: The connection to sync.
        current_user: The authenticated user.
        db: Async database session.
        client: Shared HTTP client.

    Returns:
        What the sync did.
    """
    result = await job_service.sync_connection(
        db, user_id=current_user.id, connection_id=connection_id, client=client
    )
    return SyncResultResponse.model_validate(result)


@router.delete("/sources/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    connection_id: int, current_user: CurrentUser, db: DbSession
) -> None:
    """Stop watching a board. Postings already saved from it are kept.

    Args:
        connection_id: The connection to remove.
        current_user: The authenticated user.
        db: Async database session.
    """
    await job_service.delete_connection(
        db, user_id=current_user.id, connection_id=connection_id
    )
