# lease_expires_at

Demonstrates §9.5 — `lease_constraints.expires_at` and the runtime
watchdog that emits `job.error{LEASE_EXPIRED}` on elapse.

```
python examples/lease_expires_at/server.py     # terminal 1
python examples/lease_expires_at/client.py     # terminal 2
```

Advertised features: `["lease_expires_at"]`. Client success: terminal
`job.error { code: "LEASE_EXPIRED" }` arrives within seconds.
