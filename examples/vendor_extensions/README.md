# vendor_extensions

Demonstrates spec §8.2 / §9.2 / §15: an agent emits an
`x-vendor.acme.progress` event kind and requests an
`x-vendor.acme.metrics` lease namespace. The client shows two handlers
side-by-side: a naïve one that drops unknown kinds, and a vendor-aware
one that renders them.

## Run

```sh
python examples/vendor_extensions/server.py    # terminal 1
python examples/vendor_extensions/client.py    # terminal 2
```

Client exits 0 when the naïve handler drops at least one unknown kind
and the vendor-aware handler renders at least one
`x-vendor.acme.progress`.
