"""Tests for the administrative command line (python -m src.cli)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src import cli
from src.domain.users.entities import UserEntity
from src.infrastructure.database.postgres.models import Tenant, User
from src.libs.enums.user import UserRole

PASSWORD = "correct horse battery"
ARGS = ["create-admin", "--organisation", "ACME", "--username", "root"]
ARGS += ["--email", "root@example.com"]


def tenant_lookup_finds(session: AsyncMock, tenant: Tenant | None = None) -> None:
    """Make the session's tenant lookup by organisation find `tenant`."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session.execute.return_value = result


@pytest.fixture
def hasher() -> MagicMock:
    hasher = MagicMock()
    hasher.hash.side_effect = lambda password: f"hashed:{password}"
    return hasher


class TestCreateAdmin:
    """create_admin() stores a new tenant and its first admin in one session."""

    async def test_creates_tenant_and_admin_with_hashed_password(
        self, mock_db_session: AsyncMock, hasher: MagicMock
    ):
        """
        GIVEN an organisation and the admin's name, email and password
        WHEN the admin is created
        THEN a tenant and a user with only the ADMIN role are added to the session
        AND the user's local credential holds the password hash, not the password
        """
        tenant_lookup_finds(mock_db_session)

        admin = await cli.create_admin(
            mock_db_session,
            hasher,
            organisation="ACME",
            username="root",
            email="root@example.com",
            password=PASSWORD,
        )

        tenant, user = (call.args[0] for call in mock_db_session.add.call_args_list)
        assert isinstance(tenant, Tenant) and tenant.organisation == "ACME"
        assert isinstance(user, User) and user.tenant_id == tenant.tenant_id
        assert admin is not None and admin.roles == [UserRole.ADMIN]
        assert user.credentials[0].password_hash == f"hashed:{PASSWORD}"

    async def test_existing_organisation_changes_nothing(
        self, mock_db_session: AsyncMock, hasher: MagicMock
    ):
        """
        GIVEN a tenant with the organisation name exists already
        WHEN the admin is created again (for example a second start-up script run)
        THEN nothing is added to the session AND None is returned
        AND no password is hashed
        """
        tenant_lookup_finds(
            mock_db_session, Tenant(tenant_id=uuid.uuid4(), organisation="ACME")
        )

        admin = await cli.create_admin(
            mock_db_session,
            hasher,
            organisation="ACME",
            username="root",
            email="root@example.com",
            password=PASSWORD,
        )

        assert admin is None
        mock_db_session.add.assert_not_called()
        hasher.hash.assert_not_called()


class TestMain:
    """main() validates the input like the API and never takes the password as argument."""

    def test_password_from_environment_is_used(self, monkeypatch):
        """
        GIVEN the password in VERITYGRAPH_ADMIN_PASSWORD
        WHEN create-admin runs
        THEN the admin is created with that password and the exit code is 0
        """
        monkeypatch.setenv(cli.PASSWORD_ENV, PASSWORD)

        with patch.object(cli, "run_create_admin", new=AsyncMock()) as run:
            assert cli.main(ARGS) == 0

        assert run.await_args is not None
        request = run.await_args.args[0]
        assert request.email == "root@example.com"
        assert request.password.get_secret_value() == PASSWORD

    def test_password_is_prompted_twice_without_environment(self, monkeypatch):
        """
        GIVEN no password in the environment
        WHEN create-admin runs
        THEN the password is read twice from a hidden prompt
        """
        monkeypatch.delenv(cli.PASSWORD_ENV, raising=False)

        with (
            patch.object(cli, "getpass", side_effect=[PASSWORD, PASSWORD]) as prompt,
            patch.object(cli, "run_create_admin", new=AsyncMock()),
        ):
            assert cli.main(ARGS) == 0

        assert prompt.call_count == 2

    def test_different_confirmation_fails(self, monkeypatch, capsys):
        """
        GIVEN a prompted password and a different confirmation
        WHEN create-admin runs
        THEN nothing is created AND the exit code is 2
        """
        monkeypatch.delenv(cli.PASSWORD_ENV, raising=False)

        with (
            patch.object(cli, "getpass", side_effect=[PASSWORD, "something else!"]),
            patch.object(cli, "run_create_admin", new=AsyncMock()) as run,
            pytest.raises(SystemExit) as exit_info,
        ):
            cli.main(ARGS)

        assert exit_info.value.code == 2
        run.assert_not_awaited()
        assert "do not match" in capsys.readouterr().err

    def test_invalid_input_fails_like_the_api(self, monkeypatch, capsys):
        """
        GIVEN a password shorter than the API allows
        WHEN create-admin runs
        THEN nothing is created AND the exit code is 2
        AND the error names the field but not the password
        """
        monkeypatch.setenv(cli.PASSWORD_ENV, "short")

        with (
            patch.object(cli, "run_create_admin", new=AsyncMock()) as run,
            pytest.raises(SystemExit) as exit_info,
        ):
            cli.main(ARGS)

        assert exit_info.value.code == 2
        run.assert_not_awaited()
        error = capsys.readouterr().err
        assert "password" in error
        assert "short" not in error  # the rejected value is never printed


class TestRunCreateAdmin:
    """run_create_admin() commits once, reports the outcome and disposes the engine."""

    async def run(
        self, mock_db_session: AsyncMock, admin: UserEntity | None
    ) -> AsyncMock:
        """Run the command with `create_admin` returning `admin`; return the engine."""
        engine = AsyncMock()
        request = cli.RegisterRequest.model_validate(
            {"username": "root", "email": "root@example.com", "password": PASSWORD}
        )
        with (
            patch.object(cli, "create_async_db_engine", return_value=engine),
            patch.object(
                cli, "create_session_factory", return_value=lambda: mock_db_session
            ),
            patch.object(cli, "create_admin", new=AsyncMock(return_value=admin)),
        ):
            await cli.run_create_admin(request, "ACME")
        return engine

    async def test_new_admin_is_committed(
        self, mock_db_session: AsyncMock, user_entity: UserEntity, capsys
    ):
        """
        GIVEN an organisation that does not exist yet
        WHEN the command runs against the configured database
        THEN the session commits AND the engine is disposed
        AND the output names the new tenant and admin
        """
        engine = await self.run(mock_db_session, user_entity)

        mock_db_session.commit.assert_awaited_once()
        engine.dispose.assert_awaited_once()
        output = capsys.readouterr().out
        assert str(user_entity.tenant_id) in output and user_entity.email in output

    async def test_existing_organisation_is_reported_unchanged(
        self, mock_db_session: AsyncMock, capsys
    ):
        """
        GIVEN the organisation exists already
        WHEN the command runs
        THEN nothing is committed AND the engine is disposed
        AND the output says that nothing changed
        """
        engine = await self.run(mock_db_session, None)

        mock_db_session.commit.assert_not_awaited()
        engine.dispose.assert_awaited_once()
        assert "exists already" in capsys.readouterr().out


class TestSeedDemo:
    """seed_demo() stores a demo tenant with an admin and a member."""

    async def test_creates_admin_and_member_with_random_passwords(
        self, mock_db_session: AsyncMock, hasher: MagicMock
    ):
        """
        GIVEN no demo tenant
        WHEN the demo is seeded
        THEN the demo tenant, an ADMIN and a USER are added to the session
        AND each user gets its own random password of at least 12 characters
        AND only the password hashes are stored
        """
        tenant_lookup_finds(mock_db_session)

        passwords = await cli.seed_demo(mock_db_session, hasher)

        assert passwords is not None
        tenant, admin, member = (
            call.args[0] for call in mock_db_session.add.call_args_list
        )
        assert tenant.organisation == cli.DEMO_ORGANISATION
        assert (admin.roles, member.roles) == ([UserRole.ADMIN], [UserRole.USER])
        assert {admin.tenant_id, member.tenant_id} == {tenant.tenant_id}
        assert set(passwords) == {admin.email, member.email}
        assert len(set(passwords.values())) == 2
        assert all(len(password) >= 12 for password in passwords.values())
        for user in (admin, member):
            hashed = user.credentials[0].password_hash
            assert hashed == f"hashed:{passwords[user.email]}"

    async def test_existing_demo_tenant_changes_nothing(
        self, mock_db_session: AsyncMock, hasher: MagicMock
    ):
        """
        GIVEN the demo tenant exists already
        WHEN the demo is seeded again
        THEN nothing is added to the session AND None is returned
        """
        tenant_lookup_finds(
            mock_db_session,
            Tenant(tenant_id=uuid.uuid4(), organisation=cli.DEMO_ORGANISATION),
        )

        passwords = await cli.seed_demo(mock_db_session, hasher)

        assert passwords is None
        mock_db_session.add.assert_not_called()


class TestSeedDemoCommand:
    """The seed-demo command prints the new logins once and refuses production."""

    async def run(
        self, mock_db_session: AsyncMock, passwords: dict[str, str] | None
    ) -> AsyncMock:
        """Run the command with `seed_demo` returning `passwords`; return the engine."""
        engine = AsyncMock()
        with (
            patch.object(cli, "create_async_db_engine", return_value=engine),
            patch.object(
                cli, "create_session_factory", return_value=lambda: mock_db_session
            ),
            patch.object(cli, "seed_demo", new=AsyncMock(return_value=passwords)),
        ):
            await cli.run_seed_demo()
        return engine

    async def test_new_demo_is_committed_and_logins_are_printed(
        self, mock_db_session: AsyncMock, capsys
    ):
        """
        GIVEN no demo tenant
        WHEN the command runs
        THEN the session commits AND the engine is disposed
        AND each demo email is printed with its password
        """
        logins = {"demo-admin@example.com": "secret-one-123"}

        engine = await self.run(mock_db_session, logins)

        mock_db_session.commit.assert_awaited_once()
        engine.dispose.assert_awaited_once()
        assert "demo-admin@example.com  secret-one-123" in capsys.readouterr().out

    async def test_existing_demo_is_reported_unchanged(
        self, mock_db_session: AsyncMock, capsys
    ):
        """
        GIVEN the demo tenant exists already
        WHEN the command runs
        THEN nothing is committed AND the output says that nothing changed
        """
        await self.run(mock_db_session, None)

        mock_db_session.commit.assert_not_awaited()
        assert "exists already" in capsys.readouterr().out

    def test_main_runs_seed_demo(self, test_settings):
        """
        GIVEN a development environment
        WHEN 'seed-demo' is called
        THEN the demo is seeded and the exit code is 0
        """
        with (
            patch.object(cli, "get_settings", return_value=test_settings),
            patch.object(cli, "run_seed_demo", new=AsyncMock()) as run,
        ):
            assert cli.main(["seed-demo"]) == 0

        run.assert_awaited_once()

    def test_production_is_refused(self, test_settings, capsys):
        """
        GIVEN ENVIRONMENT=production
        WHEN 'seed-demo' is called
        THEN nothing is seeded AND the exit code is 2 with a reason
        """
        production = test_settings.model_copy(update={"environment": "production"})

        with (
            patch.object(cli, "get_settings", return_value=production),
            patch.object(cli, "run_seed_demo", new=AsyncMock()) as run,
            pytest.raises(SystemExit) as exit_info,
        ):
            cli.main(["seed-demo"])

        assert exit_info.value.code == 2
        run.assert_not_awaited()
        assert "production" in capsys.readouterr().err
