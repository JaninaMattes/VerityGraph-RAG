"""Administrative commands. Run them with `python -m src.cli <command> --help`.

create-admin creates a tenant and its first admin user. Every API endpoint needs a
token, so this is how the first user of a tenant comes to exist. The password is
read from VERITYGRAPH_ADMIN_PASSWORD or from a hidden prompt, never from the command
line, where other processes and the shell history could see it.

seed-demo creates a demo tenant with an admin and a member for local development.
Each gets a new random password, printed once. It refuses ENVIRONMENT=production.

Both commands are safe to run again: an existing tenant is left unchanged.
"""

import argparse
import asyncio
import os
import secrets
import sys
from collections.abc import Awaitable, Callable
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth.hasher import PasswordHasher
from src.domain.tenants.dataclasses import Tenant
from src.domain.tenants.service import TenantService
from src.domain.users.dataclasses import User
from src.domain.users.entities import UserEntity
from src.domain.users.service import UserService
from src.infrastructure.database.postgres.engine import create_async_db_engine
from src.infrastructure.database.postgres.repositories.tenant import (
    PostgresTenantRepository,
)
from src.infrastructure.database.postgres.repositories.user import (
    PostgresUserRepository,
)
from src.infrastructure.database.postgres.session import create_session_factory
from src.infrastructure.security.passwords import Argon2PasswordHasher
from src.libs.core.config import get_settings
from src.libs.enums.user import UserRole
from src.libs.schemas.tenant import CreateTenantRequest
from src.libs.schemas.user import RegisterRequest

PASSWORD_ENV = "VERITYGRAPH_ADMIN_PASSWORD"
DEMO_ORGANISATION = "Demo Organisation"
DEMO_ADMIN = ("demo-admin", "demo-admin@example.com")
DEMO_MEMBER = ("demo-member", "demo-member@example.com")


async def create_admin(
    session: AsyncSession,
    hasher: PasswordHasher,
    *,
    organisation: str,
    username: str,
    email: str,
    password: str,
) -> UserEntity | None:
    """Add a tenant and its admin user to `session` (not committed) and return it.

    If a tenant with this organisation exists, add nothing and return None, so a
    second run cannot create a second account with the same email.
    """
    tenants = PostgresTenantRepository(session)
    if await tenants.find_by_organisation(organisation):
        return None
    tenant = await TenantService(tenants).create(Tenant(organisation))
    return await UserService(PostgresUserRepository(session), hasher).create(
        User(username, email, password), tenant.tenant_id, roles=(UserRole.ADMIN,)
    )


async def seed_demo(
    session: AsyncSession, hasher: PasswordHasher
) -> dict[str, str] | None:
    """Add the demo tenant, its admin and a member to `session` (not committed).

    Return each demo email with its new random password, or None if the demo
    tenant exists already.
    """
    (admin_name, admin_email), (member_name, member_email) = DEMO_ADMIN, DEMO_MEMBER
    passwords = {
        email: secrets.token_urlsafe(16) for email in (admin_email, member_email)
    }
    admin = await create_admin(
        session,
        hasher,
        organisation=DEMO_ORGANISATION,
        username=admin_name,
        email=admin_email,
        password=passwords[admin_email],
    )
    if admin is None:
        return None
    await UserService(PostgresUserRepository(session), hasher).create(
        User(member_name, member_email, passwords[member_email]), admin.tenant_id
    )
    return passwords


async def _in_transaction[T](work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Run `work` in one session of the configured database; commit if it returns
    a value. Always dispose the engine."""
    engine = create_async_db_engine(get_settings())
    try:
        async with create_session_factory(engine)() as session:
            result = await work(session)
            if result:
                await session.commit()
            return result
    finally:
        await engine.dispose()


async def run_create_admin(request: RegisterRequest, organisation: str) -> None:
    """Create the admin in the configured database in one transaction."""
    admin = await _in_transaction(
        lambda session: create_admin(
            session,
            Argon2PasswordHasher(),
            organisation=organisation,
            username=request.username,
            email=request.email,
            password=request.password.get_secret_value(),
        )
    )
    if admin:
        print(f"Created tenant {admin.tenant_id} with admin {admin.email}.")
    else:
        print(f"Tenant '{organisation}' exists already. Nothing changed.")


async def run_seed_demo() -> None:
    """Seed the demo in the configured database and print its logins once."""
    passwords = await _in_transaction(
        lambda session: seed_demo(session, Argon2PasswordHasher())
    )
    if not passwords:
        print(f"Tenant '{DEMO_ORGANISATION}' exists already. Nothing changed.")
        return
    print(f"Created tenant '{DEMO_ORGANISATION}'. Log in with (shown only once):")
    for email, password in passwords.items():
        print(f"  {email}  {password}")


def read_password(parser: argparse.ArgumentParser) -> str:
    """Return the password from the environment, or prompt for it twice."""
    if password := os.environ.get(PASSWORD_ENV):
        return password
    password = getpass("Admin password: ")
    if getpass("Repeat the password: ") != password:
        parser.error("The passwords do not match.")
    return password


def main(argv: list[str] | None = None) -> int:
    """Parse the command, validate it like the API does, run it; return 0."""
    parser = argparse.ArgumentParser(prog="python -m src.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser(
        "create-admin", help="Create a tenant and its first admin user."
    )
    create.add_argument("--organisation", required=True)
    create.add_argument("--username", required=True)
    create.add_argument("--email", required=True)
    commands.add_parser(
        "seed-demo", help="Create a demo tenant with an admin and a member (dev only)."
    )
    args = parser.parse_args(argv)

    if args.command == "seed-demo":
        if get_settings().environment == "production":
            parser.error("seed-demo is for development only, not for production.")
        asyncio.run(run_seed_demo())
        return 0

    try:
        tenant = CreateTenantRequest(organisation=args.organisation)
        request = RegisterRequest.model_validate(
            {
                "username": args.username,
                "email": args.email,
                "password": read_password(parser),
            }
        )
    except ValidationError as exc:
        # Name the fields and rules only: the rejected input may be the password.
        reasons = "; ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors()
        )
        parser.error(reasons)
    asyncio.run(run_create_admin(request, tenant.organisation))
    return 0


if __name__ == "__main__":
    sys.exit(main())
