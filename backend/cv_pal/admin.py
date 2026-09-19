"""Offline account recovery, for someone locked out of their own instance.

    python -m cv_pal.admin reset-password you@example.com

Not an emailed reset: that needs an SMTP server a self-hosted instance often has none
of, and a link that cannot be delivered is a control that does nothing. This grants no
access an attacker lacks — running it needs shell access to the machine holding the
database. See `PLANNING.md` → *Password policy*.
"""

import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy import select, update

from cv_pal.database import async_session
from cv_pal.hashing import hash_password
from cv_pal.models import RefreshToken, User
from cv_pal.passwords import validate_password


async def reset_password(email: str, password: str) -> int:
    """Set an account's password and end its sessions.

    Args:
        email: The account to reset.
        password: The new password. Held to the same policy as registration.

    Returns:
        A process exit code: 0 on success, 1 when no such account exists.
    """
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No account with the address {email}.", file=sys.stderr)
            return 1

        user.hashed_password = hash_password(password)
        # The same revocation the API performs — marked, not deleted, so a token
        # presented afterwards is still recognisable as one that was withdrawn.
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await db.commit()

    print(f"Password reset for {email}. Every session has been signed out.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run the requested command.

    Args:
        argv: Arguments to parse, or None to read `sys.argv`.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(prog="python -m cv_pal.admin")
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser(
        "reset-password", help="set a password for an account that is locked out"
    )
    reset.add_argument("email")

    arguments = parser.parse_args(argv)

    # Prompted, not an argument: that would land in shell history and the process list.
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat: "):
        print("Those did not match.", file=sys.stderr)
        return 1

    try:
        validate_password(password, email=arguments.email)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    return asyncio.run(reset_password(arguments.email, password))


if __name__ == "__main__":
    raise SystemExit(main())
