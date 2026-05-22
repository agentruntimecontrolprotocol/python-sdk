# Authentication

> Spec reference: ARCP v1.1 §6.1

ARCP uses **bearer token authentication**. The client presents a token; the runtime maps it to a *principal* (a string identity). All authorization decisions use the principal.

## Static bearer verifier

For development and testing, use `StaticBearerVerifier` with a hard-coded token-to-principal map:

```python
from arcp.runtime import ARCPRuntime, RuntimeInfo, StaticBearerVerifier

runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="my-service", version="1.0.0"),
    bearer=StaticBearerVerifier({
        "alice-token": "alice@example.com",
        "bob-token": "bob@example.com",
    }),
)
```

## Custom verifier

Implement the `BearerVerifier` protocol to integrate with any auth backend:

```python
from arcp.runtime import BearerVerifier

class DatabaseVerifier:
    """Look up tokens in a database."""

    def __init__(self, db):
        self._db = db

    async def verify(self, token: str) -> str | None:
        """Return the principal, or None to reject the token."""
        row = await self._db.fetchone(
            "SELECT principal FROM api_tokens WHERE token = $1 AND revoked = false",
            token,
        )
        return row["principal"] if row else None

runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="my-service", version="1.0.0"),
    bearer=DatabaseVerifier(db),
)
```

The `verify` method is called once per session, at connect time. Returning `None` causes the runtime to close the connection with `AuthenticationError`.

## JWT verifier

```python
import jwt
from arcp.runtime import BearerVerifier

class JWTVerifier:
    def __init__(self, secret: str):
        self._secret = secret

    async def verify(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
            return payload["sub"]
        except jwt.InvalidTokenError:
            return None
```

## Accessing the principal in an agent

The session principal is available in the `JobContext`:

```python
async def my_agent(input, ctx):
    principal = ctx.principal  # e.g. "alice@example.com"
    if principal != "admin@example.com":
        raise PermissionError("admin only")
    return {"ok": True}
```

## Authorization

ARCP handles *authentication* (who are you?). *Authorization* (what can you do?) is the application's responsibility. Use `ctx.principal` to make authorization decisions inside agent functions.

## Related

- [Sessions guide](sessions.md)
- [Custom auth recipe](../recipes/custom-auth.md)
- [Provisioned credentials recipe](../recipes/provisioned-credentials.md)
- [Delegation guide](delegation.md)
