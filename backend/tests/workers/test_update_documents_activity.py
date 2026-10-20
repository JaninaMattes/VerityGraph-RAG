from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from temporalio.exceptions import ApplicationError

from src.infrastructure.workflow_execution.temporalio.models import (
    UpdateDocumentPayload,
)

# Apply to all tests in this module
pytestmark = pytest.mark.asyncio


# ==========================================================
# Temporalio: Update Document Activity
# ==========================================================


class TestUpdateDocumentActivity:
    """Grouped test suit for Document activities."""

    async def test_update_document_activty_and_check_idempotency_key(
        self, activities, mock_db_session, activity_context
    ):
        # 1. Arrange
        payload = UpdateDocumentPayload(
            document_id="123e4567-e89b-12d3-a456-426614174000",
            tenant_id="123e4567-e89b-12d3-a456-426614174001",
            size_bytes=2048,
            status="PROCESSED",
            bucket_name="test-bucket",
        )

        # Mock the repository and the returned DB entity
        mock_repo = AsyncMock()
        mock_db_entity = MagicMock()
        mock_repo.get_one.return_value = mock_db_entity

        with patch(
            "src.infrastructure.workflow_execution.temporalio.activities.PostgresDocumentRepository",
            return_value=mock_repo,
        ):
            # 2. Act
            await activities.update_document_activity(payload)

            # 3. Assert
            # Verify correct UUIDs are passed
            mock_repo.get_one.assert_awaited_once_with(
                UUID(payload.document_id), UUID(payload.tenant_id)
            )

            # Verify the correct domain method was called based on payload.status
            mock_db_entity.mark_processed.assert_called_once()

            # Verify save and commit happened
            mock_repo.update.assert_awaited_once()
            mock_db_session.commit.assert_awaited_once()

            # Verify Temporal idempotency key format
            call_kwargs = mock_repo.update.call_args.kwargs
            assert call_kwargs["idempotency_key"] == "test-run-abc-activity-123"

    @pytest.mark.asyncio
    async def test_update_document_not_found_raises_non_retryable_for_not_found_error(
        self, activities, mock_db_session, activity_context
    ):
        # 1. Arrange
        payload = UpdateDocumentPayload(
            document_id="123e4567-e89b-12d3-a456-426614174000",
            tenant_id="123e4567-e89b-12d3-a456-426614174001",
            size_bytes=2048,
            status="FAILED",
            bucket_name="test-bucket",
        )

        mock_repo = AsyncMock()
        # Simulate DB returning None (document doesn't exist)
        mock_repo.get_one.return_value = None

        with patch(
            "src.infrastructure.workflow_execution.temporalio.activities.PostgresDocumentRepository",
            return_value=mock_repo,
        ):
            # 2. Act & Assert
            with pytest.raises(ApplicationError) as exc_info:
                await activities.update_document_activity(payload)

            # Verify it's marked as non-retryable.
            # If this is False, Temporal will infinitely retry the missing document!
            assert exc_info.value.non_retryable is True
            assert exc_info.value.type == "NotFound"

            # Verify we NEVER committed or updated since it failed early
            mock_db_session.commit.assert_not_awaited()
            mock_repo.update.assert_not_awaited()
