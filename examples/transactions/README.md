# Transactions Demo

A small ledger API showing Mitsuki's transaction support:

- **`@Transactional()`**: a transfer withdraws from one account and deposits into another in one transaction, so a failed deposit undoes the withdrawal
- **`REQUIRED` propagation**: `AccountService.withdraw` and `deposit` are transactional on their own, and join the transfer's transaction when called from it
- **`REQUIRES_NEW` propagation**: every transfer request is written to an audit log in its own transaction, which is kept even when the transfer rolls back
- **`NESTED` propagation**: a batch of transfers runs each one behind a savepoint, skipping the ones that fail and keeping the rest

## Running

Start PostgreSQL:

```bash
docker compose up -d
```

Then the application, from this directory:

```bash
pip install "mitsuki[postgresql]"
python app.py
```

The API listens on `http://localhost:8000`.

## Trying It Out

Open two accounts:

```bash
curl -X POST http://localhost:8000/api/accounts \
  -H "Content-Type: application/json" \
  -d '{"owner": "alice", "balance": 100}'

curl -X POST http://localhost:8000/api/accounts \
  -H "Content-Type: application/json" \
  -d '{"owner": "bob", "balance": 50}'
```

Transfer between them:

```bash
curl -X POST http://localhost:8000/api/transfers \
  -H "Content-Type: application/json" \
  -d '{"source_id": 1, "target_id": 2, "amount": 30}'
```

Transfer to an account that doesn't exist. The withdrawal from account 1 succeeds, the deposit fails, and the whole transfer rolls back:

```bash
curl -X POST http://localhost:8000/api/transfers \
  -H "Content-Type: application/json" \
  -d '{"source_id": 1, "target_id": 99, "amount": 50}'
# {"error":"Account 99 does not exist"}

curl http://localhost:8000/api/accounts
# [{"id":1,"owner":"alice","balance":70},{"id":2,"owner":"bob","balance":80}]
```

The audit log still lists the failed attempt, because it was written in its own transaction:

```bash
curl http://localhost:8000/api/audit
```

Run a batch. The transfer of 1000 can't be covered and is skipped; the other two go through:

```bash
curl -X POST http://localhost:8000/api/transfers/batch \
  -H "Content-Type: application/json" \
  -d '{"transfers": [
        {"source_id": 2, "target_id": 1, "amount": 20},
        {"source_id": 1, "target_id": 2, "amount": 1000},
        {"source_id": 1, "target_id": 2, "amount": 10}
      ]}'
# {"completed":[true,false,true]}
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/accounts` | Open an account with an owner and a starting balance |
| `GET` | `/api/accounts` | List accounts |
| `POST` | `/api/transfers` | Transfer an amount between two accounts; `404` for a missing account, `409` for insufficient funds |
| `POST` | `/api/transfers/batch` | Run several transfers, skipping those that fail |
| `GET` | `/api/audit` | List every transfer request, including failed ones |

## Cleaning Up

```bash
docker compose down -v
```

See the [Transactions documentation](../../docs/20_transactions.md) for every option.
