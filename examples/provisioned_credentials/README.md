# Provisioned Credentials

This example runs a vendor-neutral credential provisioner. The runtime
issues one deterministic bearer credential when the job is accepted and
revokes it when the job completes.

```sh
uv run python -m examples.provisioned_credentials.server
uv run python -m examples.provisioned_credentials.client
```

The in-memory provisioner is a test double. Production adapters should
implement `CredentialProvisioner` against a gateway such as LiteLLM
without adding that vendor dependency to the SDK core.
