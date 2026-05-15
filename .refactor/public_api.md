# Public API Surface (pre-refactor)

Captured from `__all__` in `src/arcp/__init__.py`, `src/arcp/client/__init__.py`,
and `src/arcp/runtime/__init__.py`. **No symbol below may be removed or
renamed without a major bump.**

## `arcp` (top-level)

### Envelope
- `Envelope`

### Errors
- `ARCPError`, `ERROR_CODES`, `error_class_for`, `error_from_payload`
- `AgentNotAvailableError`, `AgentVersionNotAvailableError`,
  `BudgetExhaustedError`, `CancelledError`, `DuplicateKeyError`,
  `HeartbeatLostError`, `InternalError`, `InvalidRequestError`,
  `JobNotFoundError`, `LeaseExpiredError`, `LeaseSubsetViolationError`,
  `PermissionDeniedError`, `ResumeWindowExpiredError`, `TimeoutError`,
  `UnauthenticatedError`

### Messages
- `Capabilities`, `ClientInfo`, `Lease`, `LeaseConstraints`,
  `ListJobsFilter`, `RuntimeInfo`, `SessionResume`,
  `SessionWelcomePayload`
- `parse_agent_ref`, `parse_budget_amount`

### Transports
- `Transport`, `TransportClosed`, `MemoryTransport`,
  `pair_memory_transports`, `StdioTransport`, `WebSocketTransport`,
  `serve_websocket`

### Version / features
- `PROTOCOL_VERSION`, `IMPL_VERSION`, `V1_1_FEATURES`,
  `intersect_features`

## `arcp.client`
- `ARCPClient`, `AutoAckOptions`, `JobHandle`, `JobSubscription`

## `arcp.runtime`
- `ARCPRuntime`, `AuthorizationContext`, `JobAuthorizationPolicy`
- `Agent`, `Job`, `JobContext`, `ResultStream`
- `SessionContext`, `SessionState`
- `BearerVerifier`, `Identity`, `StaticBearerVerifier`, `JWTVerifier`
- `EventLog`, `InMemoryEventLog`, `SqliteEventLog`
- `LeaseOpContext`, `assert_lease_subset`, `initial_budget_from_lease`,
  `is_lease_subset`, `validate_lease_constraints`,
  `validate_lease_op`, `validate_lease_shape`

## CLI entry point
- `arcp` (console script → `arcp.cli:main`)

## Notes
- The CLI imports `ARCPClient`/`StaticBearerVerifier` from `arcp` top-level
  (mypy flags this as missing). They are *not* re-exported there today;
  the CLI relies on the dynamic re-export chain. Honor either by
  (a) keeping CLI internal, or (b) adding top-level re-exports. Choice
  documented in CHANGELOG.
