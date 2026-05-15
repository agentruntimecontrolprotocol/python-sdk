# Violations Inventory

## File length > 300 lines (Guide §0)

| File                                | Lines | Plan                                                  |
| ----------------------------------- | ----- | ----------------------------------------------------- |
| `src/arcp/_runtime/server.py`       | 744   | Split: lifecycle / dispatch / job-run / housekeeping |
| `src/arcp/_client/client.py`        | 479   | Split: connection / handshake / job ops              |
| `src/arcp/_runtime/job.py`          | 372   | Split: data classes vs. ResultStream impl            |
| `src/arcp/_messages/execution.py`   | 348   | Split: payload models / helpers / parsers            |

## Function-level violations (`ruff --select C901,PLR0913,PLR0912`)

| Location                                   | Issue                          | Plan                                |
| ------------------------------------------ | ------------------------------ | ----------------------------------- |
| `_auth/jwt.py:16` JWTVerifier.__init__     | 7 args                         | Group into `JWTVerifierConfig` dc   |
| `_client/client.py:69` ARCPClient.__init__ | 7 args                         | Group into `ClientConfig` dc        |
| `_client/client.py:183` submit             | 8 args                         | Group into `JobSubmit` dc           |
| `_client/client.py:291` _handshake         | 11 args                        | Group into `HandshakeArgs` dc       |
| `_runtime/server.py:110` __init__          | >5 args                        | Group into `RuntimeConfig` dc       |
| `_runtime/server.py:340` _dispatch         | complexity 11                  | Dict-of-handlers                    |
| `_runtime/server.py:532` _run_job          | complexity 11                  | Extract phases                      |
| `_runtime/session.py:150` make_session_state | 6 args                       | Group into `SessionParams` dc       |

## Mypy --strict errors (14 total)

| Location                                | Issue                                          | Plan                                 |
| --------------------------------------- | ---------------------------------------------- | ------------------------------------ |
| `middleware/asgi.py:48`                 | Any return on model_dump()                     | `cast(dict[str, Any], ...)`          |
| `middleware/aiohttp.py:43`              | same                                           | same                                 |
| `_transport/stdio.py:38`                | same                                           | same                                 |
| `_transport/websocket.py:46`            | same                                           | same                                 |
| `_transport/websocket.py:67`            | Any return on int|None                         | explicit cast                        |
| `_transport/websocket.py:86`            | `Server` name-defined (TYPE_CHECKING)          | proper import guard                  |
| `_messages/execution.py:67`             | unused type:ignore                             | drop comment                         |
| `_client/client.py:213`                 | Liskov: payload class union narrowing          | use match/cast                       |
| `_client/client.py:366`                 | Any return                                     | explicit cast                        |
| `_runtime/server.py:135`                | `EventLog|InMemoryEventLog` vs `EventLog`      | hoist InMemoryEventLog into hierarchy |
| `_runtime/server.py:679`                | missing await on async iter                    | `async for x in await coro`          |
| `cli.py:13`                             | missing top-level `ARCPClient`                 | import from `arcp.client`            |
| `cli.py:13`                             | missing top-level `StaticBearerVerifier`       | import from `arcp.runtime`           |
| `cli.py:48`                             | event_log subtype mismatch                     | widen param type                     |

## Coverage (60% → 90% target)

Currently 73.27%. Largest gaps:
- `_runtime/server.py` 68%
- `_runtime/session.py` 57%
- `_transport/base.py` 63%
- `_transport/in_memory.py` 84%
- `_envelope.py` (check)

## Other inventory

- `print()` in library code: **none** (verified)
- bare `except`: **none** (verified)
- wildcard imports: **none** (verified)
- mutable default args: **none flagged by ruff**
- `Optional`/`Union` style: **none** (verified — already uses `X | None`)
- `setup.py`/`setup.cfg`: **none**
- `py.typed`: **present**
- src layout: **present**

## Decisions for documented judgment calls

1. **`coverage --cov-fail-under=60` → 90.** The guide mandates 90.
   Bump in the same PR.
2. **`ruff.lint.mccabe.max-complexity` not configured.** Set to 8.
3. **`ruff.lint.pylint.max-args` not configured.** Set to 5.
4. **`pyright` is in `pyproject.toml` (strict).** Add `mypy --strict`
   alongside, keep pyright for IDEs.
5. **Doctests:** add `--doctest-modules` to default pytest invocation.
6. **`pre-commit`:** add config invoking ruff + mypy.
