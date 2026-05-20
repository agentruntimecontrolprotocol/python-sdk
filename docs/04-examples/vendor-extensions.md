---
title: "Vendor extensions"
sdk: python
order: 8
kind: example
---

A client and a runtime exchange `x-vendor.*` namespaced fields on
envelope payloads. Demonstrates the spec §5.3 forward-compatibility
contract: unknown `x-` fields pass through validators untouched.

Source: [`../../examples/vendor_extensions/`](../../examples/vendor_extensions/).

```sh
uv run python -m examples.vendor_extensions.runtime &
uv run python -m examples.vendor_extensions.client
```

## See also

- Spec: [`../../../spec/docs/draft-arcp-1.1.md`](../../../spec/docs/draft-arcp-1.1.md) §5.3.
