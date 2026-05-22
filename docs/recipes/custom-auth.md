# Custom auth

A runtime mounts a custom `BearerVerifier` that consults an external
identity store, replacing the `StaticBearerVerifier` used in the
quickstart. Demonstrates the seam between transport-level
authentication and the rest of the protocol.

Source: [`../../examples/custom_auth/`](../../examples/custom_auth/).

```sh
uv run python -m examples.custom_auth.runtime &
uv run python -m examples.custom_auth.client
```

## See also

- Guide: [Authentication](../guides/auth.md).
- Spec: [ARCP v1.1 §6.1](https://arcp.dev/spec/v1.1#section-6.1).
