---
title: "Custom auth"
sdk: python
order: 9
kind: example
---

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

- Reference: [`../05-reference/arcp-runtime.md`](../05-reference/arcp-runtime.md).
- Spec: [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md) §6.1.
