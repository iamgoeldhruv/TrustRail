
import pytest

from app.ledger.hashing import (
    GENESIS_HASH,
    compute_event_hash,
)


def sample_event() -> dict:
    return {
        "id": "event-001",
        "txn_id": "txn-001",
        "seq": 1,
        "type": "TRANSACTION_PROPOSED",
        "payload": {"issue_number": 42},
        "ts": "2026-11-05T10:30:00.000000Z",
    }


def test_compute_event_hash_returns_sha256_hex():
    result = compute_event_hash(GENESIS_HASH, sample_event())

    assert len(result) == 64
    assert all(char in "0123456789abcdef" for char in result)


def test_same_event_and_previous_hash_produce_same_hash():
    first = compute_event_hash(GENESIS_HASH, sample_event())
    second = compute_event_hash(GENESIS_HASH, sample_event())

    assert first == second


def test_dictionary_key_order_does_not_change_hash():
    event_a = sample_event()
    event_b = dict(reversed(list(event_a.items())))

    assert compute_event_hash(GENESIS_HASH, event_a) == (
        compute_event_hash(GENESIS_HASH, event_b)
    )


def test_changing_event_payload_changes_hash():
    original = sample_event()
    modified = sample_event()
    modified["payload"] = {"issue_number": 99}

    assert compute_event_hash(GENESIS_HASH, original) != (
        compute_event_hash(GENESIS_HASH, modified)
    )


def test_changing_previous_hash_changes_hash():
    event = sample_event()

    first = compute_event_hash(GENESIS_HASH, event)
    second = compute_event_hash("a" * 64, event)

    assert first != second


def test_changing_sequence_changes_hash():
    original = sample_event()
    modified = sample_event()
    modified["seq"] = 2

    assert compute_event_hash(GENESIS_HASH, original) != (
        compute_event_hash(GENESIS_HASH, modified)
    )


def test_event_data_cannot_include_hash_fields():
    with pytest.raises(ValueError, match="reserved fields"):
        compute_event_hash(
            GENESIS_HASH,
            {**sample_event(), "hash": "fake"},
        )


def test_event_data_cannot_include_previous_hash():
    with pytest.raises(ValueError, match="reserved fields"):
        compute_event_hash(
            GENESIS_HASH,
            {**sample_event(), "prev_hash": GENESIS_HASH},
        )


@pytest.mark.parametrize("invalid_hash", ["", "abc", "g" * 64, "A" * 64])
def test_invalid_previous_hash_is_rejected(invalid_hash):
    with pytest.raises(ValueError, match="Previous hash"):
        compute_event_hash(invalid_hash, sample_event())


def test_non_mapping_event_data_is_rejected():
    with pytest.raises(TypeError, match="mapping"):
        compute_event_hash(GENESIS_HASH, ["not", "a", "mapping"])
