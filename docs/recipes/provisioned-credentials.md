# Provisioned credentials

A runtime installs an `InMemoryCredentialProvisioner`, advertises
`model.use` and `provisioned_credentials`, and accepts a job whose
lease scopes the generated credential to `tier-fast/*` and `USD:1.00`.

Source: [`../../examples/provisioned_credentials/`](../../examples/provisioned_credentials/).

```sh
uv run python -m examples.provisioned_credentials.server &
uv run python -m examples.provisioned_credentials.client
```

## See also

- Guide: [Authentication](../guides/auth.md).
- Guide: [Leases](../guides/leases.md).
