"""Development automation sessions."""

from pathlib import Path

import nox

nox.options.sessions = ["lint", "typecheck", "tests", "migrations"]
nox.options.default_venv_backend = "uv"

PYTHON_VERSION = "3.14"
SOURCES = ("cv_pal", "tests", "noxfile.py")


def install_locked(session: nox.Session) -> None:
    """Install exactly what ``uv.lock`` pins, into the session's virtualenv.

    The same versions CI installs. Resolving afresh instead let a new release of a
    dependency fail the gate here while CI stayed green, and the other way round.
    """
    session.run_install(
        "uv",
        "sync",
        "--locked",
        "--extra",
        "dev",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session(python=PYTHON_VERSION)
def lint(session: nox.Session) -> None:
    """Run ruff linter and formatter checks."""
    install_locked(session)
    session.run("ruff", "check", *SOURCES)
    session.run("ruff", "format", "--check", *SOURCES)


@nox.session(python=PYTHON_VERSION)
def format(session: nox.Session) -> None:  # noqa: A001  # nox exposes the session name
    """Apply ruff formatting and safe autofixes."""
    install_locked(session)
    session.run("ruff", "check", "--fix", *SOURCES)
    session.run("ruff", "format", *SOURCES)


@nox.session(python=PYTHON_VERSION)
def typecheck(session: nox.Session) -> None:
    """Run mypy strict type checking."""
    install_locked(session)
    session.run("mypy", "--strict", "cv_pal", "tests")


@nox.session(python=PYTHON_VERSION)
def tests(session: nox.Session) -> None:
    """Run the pytest suite."""
    install_locked(session)
    session.run("pytest", *session.posargs)


@nox.session(python=PYTHON_VERSION)
def migrations(session: nox.Session) -> None:
    """Check the migrations apply, match the models, and roll back.

    ``alembic check`` catches the one thing the test suite cannot: a model changed
    without a migration. Tests build their schema from the models directly, so they pass
    whether or not a migration exists for the change — and the mismatch only surfaces
    against a real database, which by then is somebody's deployment.

    Runs against a throwaway SQLite file so it leaves nothing behind.
    """
    install_locked(session)
    database = Path(session.create_tmp()) / "migrations.db"
    env = {
        "CV_PAL_SECRET_KEY": "nox-migration-check-not-a-real-secret",
        "CV_PAL_LLM_PROVIDER": "ollama",
        "CV_PAL_DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    }
    session.run("alembic", "upgrade", "head", env=env)
    session.run("alembic", "check", env=env)
    session.run("alembic", "downgrade", "base", env=env)
