# syntax=docker/dockerfile:1

# Build stage: resolve dependencies with uv against the committed lock file.
FROM python:3.14-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so a source-only change does not re-resolve the whole tree.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev


# Runtime stage: no uv, no build tooling, no dev dependencies.
FROM python:3.14-slim AS runtime

# Runs unprivileged. A container escape should not begin as root.
RUN groupadd --system cvpal \
    && useradd --system --gid cvpal --home-dir /app --shell /usr/sbin/nologin cvpal

WORKDIR /app

COPY --from=builder --chown=cvpal:cvpal /app /app
COPY --chown=cvpal:cvpal docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# The database and uploads live here. Creating it with the right ownership before
# declaring the volume means Docker seeds a fresh named volume with that ownership,
# so the unprivileged process can write to it.
RUN mkdir -p /data/uploads && chown -R cvpal:cvpal /data
VOLUME ["/data"]

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CV_PAL_DATABASE_URL="sqlite+aiosqlite:////data/cv_pal.db" \
    CV_PAL_UPLOAD_DIR="/data/uploads"

USER cvpal
EXPOSE 8000

# Liveness only — readiness additionally touches the database, which would make a
# transient database blip restart a healthy container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live').read()"]

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "cv_pal.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--forwarded-allow-ips", "*"]
