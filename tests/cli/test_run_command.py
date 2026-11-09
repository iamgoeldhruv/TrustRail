from app.cli.commands.run import _create_run
from app.cli.main import build_parser
from app.db.connection import get_connection
from app.db.migrations import run_migrations
from app.ledger.store import LedgerStore
from app.policy.models import CompiledPolicyResponse


def _compiled_policy() -> CompiledPolicyResponse:
    return CompiledPolicyResponse.model_validate(
        {
            "policy": {
                "version": 1,
                "repo": "owner/repo",
                "actions": {
                    "close_issue": {
                        "allowed": True,
                        "conditions": {
                            "inactive_days_gte": 30,
                            "priority_not_in": ["P0"],
                            "require_priority_label": True,
                        },
                        "requires_approval": True,
                    }
                },
                "limits": {"max_actions_per_run": 10},
                "audit": {"enabled": True},
            },
            "summary": "Close inactive issues.",
        }
    )


def test_run_command_accepts_policy_and_request() -> None:
    args = build_parser().parse_args(
        [
            "run",
            "--policy",
            "Only close inactive issues.",
            "--request",
            "Find eligible issues.",
        ]
    )

    assert args.command == "run"
    assert args.policy == "Only close inactive issues."
    assert args.request == "Find eligible issues."


def test_create_run_persists_policy_request_and_run_event(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "run.db"
    monkeypatch.setattr("app.cli.commands.run.settings.tr_db_path", str(db_path))
    monkeypatch.setattr(
        "app.cli.commands.run.settings.tr_planner_model",
        "planner-test",
    )
    run_migrations(db_path=db_path)

    policy_id, run_id = _create_run(
        policy_request="Only close inactive issues.",
        user_request="Find eligible issues.",
        compiled=_compiled_policy(),
    )

    with get_connection(db_path) as connection:
        policy = connection.execute(
            "SELECT nl_text FROM policies WHERE id = ?",
            (policy_id,),
        ).fetchone()
        run = connection.execute(
            "SELECT user_request, planner_model FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()

    assert policy["nl_text"] == "Only close inactive issues."
    assert run["user_request"] == "Find eligible issues."
    assert run["planner_model"] == "planner-test"
    assert LedgerStore(db_path).verify_chain(run_id).valid is True
