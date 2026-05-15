# progress

Demonstrates the §8.2.1 `progress` event kind.

```
python examples/progress/server.py     # terminal 1
python examples/progress/client.py     # terminal 2
```

Advertised features: `["progress"]`. Client success: ≥ 5 progress events
observed; final `current == total`.
