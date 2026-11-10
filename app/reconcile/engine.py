import json
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from app.otari.exceptions import OtariMCPError
from app.otari.mcp import OtariMCPClient
from app.reconcile.classifier import classify_reconciliation
from app.reconcile.models import (
    IssueActivityEvidence,
    ReconciliationOutcome,
    ReconciliationResult,
)
from app.txn.states import TransactionState
from app.txn.store import TransactionStore


SUPPORTED_WRITE_TOOL = "close_issue_with_note"
RECONCILIATION_TOOL = "get_issue_activity"


class ReconciliationError(Exception):
    """Raised when a transaction cannot be reconciled."""


class _ProbeFailure(ReconciliationError):
    """A probe failure that retains the Otari Request ID, if available."""

    def __init__(
        self,
        message: str,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.otari_request_id = request_id


class ReconciliationEngine:
    """
    Reconciles uncertain GitHub writes using read-only GitHub activity.

    Safety guarantees:
    - Never invokes the original write tool.
    - Never retries the original write.
    - Uses persisted transaction arguments.
    - Uses the current MCP server revision for read-only execution.
    - Treats missing or malformed evidence as a probe failure.
    - Persists reconciliation outcomes and evidence through TransactionStore.
    """

    def __init__(
        self,
        *,
        store: TransactionStore,
        otari_client: OtariMCPClient,
        server_id: str,
        expected_repository: str,
    ) -> None:
        if not server_id.strip():
            raise ValueError("Otari MCP server ID cannot be empty")

        if not expected_repository.strip():
            raise ValueError("Expected repository cannot be empty")

        self.store = store
        self.otari_client = otari_client
        self.server_id = server_id
        self.expected_repository = expected_repository

    async def reconcile(
        self,
        transaction_id: str,
    ) -> ReconciliationResult:
        """
        Reconcile an INDETERMINATE or UNRESOLVED transaction.

        Flow:
            1. Load persisted transaction.
            2. Validate supported write tool and arguments.
            3. Atomically claim reconciliation.
            4. Discover the current Otari MCP server revision.
            5. Execute the read-only get_issue_activity tool.
            6. Validate returned evidence.
            7. Classify the outcome deterministically.
            8. Persist the outcome and evidence atomically.
        """

        # ---------------------------------------------------------
        # 1. Load the persisted transaction.
        # ---------------------------------------------------------

        transaction = self.store.get_transaction(transaction_id)

        if transaction is None:
            raise ReconciliationError(f"Transaction {transaction_id} does not exist")

        # ---------------------------------------------------------
        # 2. Validate the transaction before claiming it.
        # ---------------------------------------------------------

        if transaction.tool != SUPPORTED_WRITE_TOOL:
            raise ReconciliationError(f"Unsupported reconciliation tool: {transaction.tool}")

        issue_number = self._get_issue_number(transaction.args)

        # ---------------------------------------------------------
        # 3. Atomically claim reconciliation.
        # ---------------------------------------------------------

        previous_state = self.store.claim_for_reconciliation(transaction_id)

        if previous_state is None:
            raise ReconciliationError(
                "Transaction is not eligible for reconciliation, "
                "or another reconciliation attempt already claimed it"
            )

        # claim_for_reconciliation() only permits:
        # INDETERMINATE -> RECONCILING
        # UNRESOLVED -> RECONCILING
        #
        # It is responsible for validating this transition atomically.

        request_id: str | None = None

        # ---------------------------------------------------------
        # 4-7. Probe, validate, and classify.
        # ---------------------------------------------------------

        try:
            evidence, request_id = await self._probe(
                transaction_id=transaction_id,
                issue_number=issue_number,
            )

            # Verify the evidence belongs to the configured repository.
            if evidence.repository != self.expected_repository:
                raise ValueError(
                    "GitHub evidence repository does not match the configured repository"
                )

            # Verify the evidence refers to the persisted issue.
            if evidence.issue_number != issue_number:
                raise ValueError(
                    "GitHub evidence issue number does not match "
                    "the persisted transaction arguments"
                )

            # Deterministic classification. No LLM involvement.
            outcome = classify_reconciliation(
                transaction_id,
                evidence,
            )

            # The classifier already returns TransactionState.
            # No string-to-enum conversion or mapping is necessary.
            target_state = outcome

            reason = self._build_reason(
                outcome=outcome,
                evidence=evidence,
            )

        except Exception as exc:
            # Preserve a Request ID from an Otari exception or probe failure.
            request_id = (
                getattr(exc, "otari_request_id", None)
                or getattr(exc, "request_id", None)
                or request_id
            )

            # Restore the original uncertain state.
            #
            # This operation also records the failed reconciliation attempt.
            # If persistence fails, allow that failure to propagate.
            self.store.fail_reconciliation_attempt(
                transaction_id,
                previous_state,
                error_code=self._error_code(exc),
                otari_request_id=request_id,
            )

            raise ReconciliationError(f"Reconciliation probe failed: {exc}") from exc

        # ---------------------------------------------------------
        # 8. Persist the reconciliation outcome.
        # ---------------------------------------------------------
        #
        # Intentionally outside the probe try/except.
        #
        # A database/ledger failure here must not be interpreted as a
        # probe failure or trigger fail_reconciliation_attempt().

        self.store.complete_reconciliation(
            transaction_id,
            target_state,
            evidence=evidence.model_dump(mode="json"),
            reason=reason,
            otari_request_id=request_id,
        )

        return ReconciliationResult(
            transaction_id=transaction_id,
            outcome=outcome,
            reason=reason,
            evidence=evidence,
        )

    async def _probe(
        self,
        *,
        transaction_id: str,
        issue_number: int,
    ) -> tuple[IssueActivityEvidence, str | None]:
        """
        Execute the read-only GitHub activity probe through Otari.

        A fresh discovery is performed for every reconciliation attempt.
        The current server revision is used because this operation only
        collects evidence; it does not authorize or repeat a write.
        """

        # Discover the currently configured MCP server.
        discovery = await self.otari_client.discover(self.server_id)

        self.store.record_otari_request_id(
            transaction_id,
            discovery.otari_request_id,
        )

        # Verify that the read-only tool is available.
        available_tools = {self._tool_name(tool) for tool in discovery.tools}

        if RECONCILIATION_TOOL not in available_tools:
            raise ReconciliationError(f"Otari MCP server does not expose {RECONCILIATION_TOOL}")

        # Execute exactly one read-only probe.
        #
        # IMPORTANT:
        # - Never call close_issue_with_note here.
        # - Use the persisted transaction ID as txn_id.
        # - Generate a fresh client_execution_id for this probe.
        response = await self.otari_client.execute(
            server_id=self.server_id,
            tool_name=RECONCILIATION_TOOL,
            arguments={
                "issue_number": issue_number,
                "txn_id": transaction_id,
            },
            server_revision=discovery.server_revision,
            client_execution_id=uuid4(),
        )
        # self.store.record_otari_request_id(
        #     transaction_id,
        #     discovery.otari_request_id,
        # )
        request_id = response.otari_request_id

        # An MCP tool-level error is not evidence that the original
        # write failed. Preserve uncertainty and allow reconciliation
        # to be attempted again later.
        if response.isError:
            raise _ProbeFailure(
                "Otari returned an MCP tool execution error",
                request_id,
            )

        # Parse and validate evidence.
        try:
            evidence_payload = self._extract_structured_content(response)

            evidence = IssueActivityEvidence.model_validate(evidence_payload)

        except Exception as exc:
            raise _ProbeFailure(
                f"Invalid GitHub activity evidence: {exc}",
                request_id,
            ) from exc

        return evidence, request_id

    @staticmethod
    def _get_issue_number(args: Any) -> int:
        """Extract a valid issue number from persisted transaction args."""

        if not isinstance(args, Mapping):
            raise ReconciliationError("Persisted transaction arguments must be an object")

        value = args.get("issue_number")

        # bool is a subclass of int in Python.
        # Explicitly reject True and False.
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ReconciliationError("Persisted transaction has an invalid issue_number")

        return value

    @staticmethod
    def _tool_name(tool: Any) -> str:
        """Extract a tool name from a dictionary or Pydantic model."""

        if isinstance(tool, Mapping):
            name = tool.get("name")
        else:
            name = getattr(tool, "name", None)

        return name if isinstance(name, str) else ""

    @staticmethod
    def _extract_structured_content(
        response: Any,
    ) -> dict[str, Any]:
        """
        Extract the GitHub evidence from an Otari MCP response.

        structuredContent is the preferred source.

        JSON text content is a fallback for MCP servers that do not
        provide structuredContent.

        Missing or malformed evidence must never become NOT_EXECUTED.
        """

        structured_content = response.structuredContent

        if structured_content is not None:
            if not isinstance(structured_content, dict):
                raise ValueError("MCP structuredContent must be a JSON object")

            return structured_content

        # Fallback: inspect text content for a JSON object.
        for content_item in response.content:
            if not isinstance(content_item, Mapping):
                continue

            if content_item.get("type") != "text":
                continue

            text_content = content_item.get("text")

            if not isinstance(text_content, str):
                continue

            try:
                parsed = json.loads(text_content)
            except json.JSONDecodeError:
                continue

            if isinstance(parsed, dict):
                return parsed

        raise ValueError("MCP response contained no usable structured evidence")

    @staticmethod
    def _build_reason(
        *,
        outcome: ReconciliationOutcome,
        evidence: IssueActivityEvidence,
    ) -> str:
        """Build a human-readable explanation of the classification."""

        # Use TransactionState enum members as dictionary keys.
        # Do not use strings such as "SUCCEEDED" here.
        reasons: dict[ReconciliationOutcome, str] = {
            TransactionState.SUCCEEDED: (
                "Issue is closed and exactly one transaction marker exists."
            ),
            TransactionState.NOT_EXECUTED: ("Issue is open and no transaction marker exists."),
            TransactionState.UNRESOLVED: (
                "Issue state and transaction marker evidence are inconsistent."
            ),
            TransactionState.DUPLICATE_DETECTED: (
                "Multiple transaction markers exist for the same transaction."
            ),
        }

        return (
            f"{reasons[outcome]} "
            f"issue_state={evidence.issue_state}, "
            f"marker_count={evidence.marker_comment_count}."
        )

    @staticmethod
    def _error_code(exc: Exception) -> str:
        """Extract a stable error code for the transaction ledger."""

        if isinstance(exc, OtariMCPError):
            code = getattr(exc, "code", None)

            if code:
                return str(code)

        return type(exc).__name__
