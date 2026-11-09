from app.ledger.store import LedgerStore

TXN_ID = "demo-txn-77cb0dca-2934-43d8-b3ec-4973dae0df59"


def main() -> None:
    store = LedgerStore()
    result = store.verify_chain(TXN_ID)

    print("=== TRUSTRAIL LEDGER VERIFICATION ===")
    print(f"Transaction ID: {result.txn_id}")
    print(f"Valid: {result.valid}")
    print(f"Events checked: {result.events_checked}")
    print(f"First invalid sequence: {result.first_invalid_seq}")
    print(f"Reason: {result.reason}")

    if not result.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()