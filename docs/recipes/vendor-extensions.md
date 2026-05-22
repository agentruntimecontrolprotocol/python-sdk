# Vendor extensions

A client and a runtime exchange `x-vendor.*` namespaced fields on
envelope payloads. Demonstrates the spec §5.3 forward-compatibility
contract: unknown `x-` fields pass through validators untouched.

Source: [`../../examples/vendor_extensions/`](../../examples/vendor_extensions/).

```sh
uv run python -m examples.vendor_extensions.runtime &
uv run python -m examples.vendor_extensions.client
```

## See also

- Guide: [Vendor extensions](../guides/vendor-extensions.md).
- Spec: [ARCP v1.1 §15](https://arcp.dev/spec/v1.1#section-15).
