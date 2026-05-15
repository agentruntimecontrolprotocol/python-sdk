# custom_auth

Demonstrates spec §6.1: a `BearerVerifier` implementation that validates
stateless HMAC-signed `principal.exp.hmac` tokens. Bad tokens are
rejected with `UNAUTHENTICATED` at handshake time.

## Run

```sh
python examples/custom_auth/server.py    # terminal 1
python examples/custom_auth/client.py    # terminal 2
```

Client exits 0 when one valid-token submit succeeds and one bad-token
connection raises `UnauthenticatedError`.
