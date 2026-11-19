"""Administrative commands. Run them with `python -m src.cli <command> --help`.

create-admin creates a tenant and its first admin user. Every API endpoint needs a
token, so this is how the first user of a tenant comes to exist. The password is
read from VERITYGRAPH_ADMIN_PASSWORD or from a hidden prompt, never from the command
line, where other processes and the shell history could see it.
"""

import argparse
import asyncio
import os
import sys
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


async def create_admin(
    session: AsyncSession,
    hasher: PasswordHasher,
    *,
    organisation: str,
    username: str,
    email: str,
    password: str,
) -> UserEntity:
    """Add a tenant and its admin user to `session` (not committed) and return it."""
    tenant = await TenantService(PostgresTenantRepository(session)).create(
        Tenant(organisation)
    )
    return await UserService(PostgresUserRepository(session), hasher).create(
        User(username, email, password), tenant.tenant_id, roles=(UserRole.ADMIN,)
    )


async def run_create_admin(request: RegisterRequest, organisation: str) -> None:
    """Create the admin in the configured database in one transaction."""
    engine = create_async_db_engine(get_settings())
    try:
        async with create_session_factory(engine)() as session:
            admin = await create_admin(
                session,
                Argon2PasswordHasher(),
                organisation=organisation,
                username=request.username,
                email=request.email,
                password=request.password.get_secret_value(),
            )
            await session.commit()
    finally:
        await engine.dispose()
    print(f"Created tenant {admin.tenant_id} with admin {admin.email}.")


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
    args = parser.parse_args(argv)

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
