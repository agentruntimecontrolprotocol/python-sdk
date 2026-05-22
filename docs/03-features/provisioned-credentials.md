---
title: "Provisioned credentials"
sdk: python
spec_sections: ["§9.7", "§9.8", "§14"]
order: 11
kind: feature
---

## What it is

`model.use` constrains which upstream model identifiers a job may
use. When a runtime is configured with a credential provisioner, it
can mint short-lived credentials scoped to the job's `cost.budget`,
`model.use`, and `lease_constraints.expires_at`, then attach them to
`job.accepted.payload.credentials`.

Credentials are issued only for the submitting session and are
revoked when the job reaches any terminal state. List and subscribe
surfaces intentionally omit credential values.

## Feature flags

- `model.use`
- `provisioned_credentials`

The runtime advertises these flags only when `credential_provisioner`
and `revocation_log` are configured.

## Python API

```python
runtime = ARCPRuntime(
    runtime=RuntimeInfo(name="demo", version="1.1.0"),
    bearer=StaticBearerVerifier({"demo-token": "p1"}),
    credential_provisioner=InMemoryCredentialProvisioner(),
    revocation_log=InMemoryRevocationLog(),
)

handle = await client.submit(
    agent="summarize",
    lease_request={
        "model.use": ["tier-fast/*"],
        "cost.budget": ["USD:5.00"],
    },
)

credential = handle.credentials[0]
```

Inside an agent, call `ctx.authorize_model("tier-fast/mini")` before
using a model id when the runtime is in the call path. Provisioner
adapters can translate upstream budget failures by raising
`UpstreamBudgetExhausted`; the runtime emits `BUDGET_EXHAUSTED`.

## See also

- Example: [`../04-examples/provisioned-credentials.md`](../04-examples/provisioned-credentials.md).
- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §§9.7–9.8.
