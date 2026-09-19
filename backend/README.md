# CV Pal — backend

FastAPI service: auth, CV storage, and AI-assisted CV review.

```bash
uv sync --extra dev
cp .env.example .env             # then set CV_PAL_SECRET_KEY
uv run alembic upgrade head
uv run uvicorn cv_pal.main:app --reload   # http://localhost:8000/docs
uv run nox                                # ruff + mypy --strict + pytest
```

Full setup and troubleshooting: [../docs/development.md](../docs/development.md)