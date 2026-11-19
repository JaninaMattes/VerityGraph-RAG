"""Tests for the administrative command line (python -m src.cli)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src import cli
from src.infrastructure.database.postgres.models import Tenant, User
from src.libs.enums.user import UserRole

PASSWORD = "correct horse battery"
ARGS = ["create-admin", "--organisation", "ACME", "--username", "root"]
ARGS += ["--email", "root@example.com"]


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
        assert admin.roles == [UserRole.ADMIN]
        assert user.credentials[0].password_hash == f"hashed:{PASSWORD}"


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
    """run_create_admin() commits once and always disposes the engine."""

    async def test_commits_and_disposes(self, mock_db_session: AsyncMock):
        """
        GIVEN a valid request
        WHEN the command runs against the configured database
        THEN the session commits AND the engine is disposed
        """
        engine = AsyncMock()
        request = cli.RegisterRequest.model_validate(
            {"username": "root", "email": "root@example.com", "password": PASSWORD}
        )

        with (
            patch.object(cli, "create_async_db_engine", return_value=engine),
            patch.object(
                cli, "create_session_factory", return_value=lambda: mock_db_session
            ),
            patch.object(cli, "create_admin", new=AsyncMock()) as create,
        ):
            await cli.run_create_admin(request, "ACME")

        create.assert_awaited_once()
        mock_db_session.commit.assert_awaited_once()
        engine.dispose.assert_awaited_once()
