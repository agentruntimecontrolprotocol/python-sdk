# Delegation

> Spec reference: ARCP v1.1 §10

**Delegation** allows an agent acting as a client to downstream runtimes to carry the original caller's identity. This creates a verifiable trust chain: the downstream runtime can see who originally initiated the work.

## Basic pattern

```
Alice ──► Runtime A  ──►  Runtime B
        (agent A)         (agent B)
```

Agent A on Runtime A submits a job to Runtime B. Runtime B sees Alice as the delegated principal, not agent A's service identity.

## Creating a delegation token

On Runtime A, inside the agent function:

```python
async def orchestrator(input, ctx):
    # Create a scoped delegation token for the downstream call
    token = ctx.create_delegation_token(
        scopes=["summarise"],      # restrict to specific agents
        expires_in_s=60,
    )

    # Connect to Runtime B with the delegation token
    client_b = ARCPClient(
        client=ClientInfo(name="orchestrator", version="1.0.0"),
        token=token,
    )
    await client_b.connect(runtime_b_transport)

    handle = await client_b.submit(agent="summarise", input=input)
    result = await handle.done
    await client_b.close()

    return result.result
```

## Verifying delegation on Runtime B

Runtime B automatically validates delegation tokens if configured with the same signing key:

```python
runtime_b = ARCPRuntime(
    runtime=RuntimeInfo(name="runtime-b", version="1.0.0"),
    bearer=StaticBearerVerifier({"service-token": "service@example.com"}),
    delegation_secret="shared-signing-key",  # must match Runtime A
)
```

Inside agent B, `ctx.principal` will be Alice's identity, and `ctx.delegated_by` will be the orchestrator's identity.

```python
async def summarise(input, ctx):
    print(ctx.principal)       # "alice@example.com"
    print(ctx.delegated_by)    # "orchestrator@service.example.com"
    ...
```

## Delegation depth

ARCP supports multi-hop delegation (A → B → C). Each hop appends to a delegation chain. The chain is validated at each runtime.

## Restricting delegation scope

```python
token = ctx.create_delegation_token(
    scopes=["summarise", "translate"],  # only these agents may be called
    max_hops=2,                          # chain depth limit
    expires_in_s=120,
)
```

Attempting to call an out-of-scope agent raises `AuthorizationError`.

## Related

- [Auth guide](auth.md)
- [Delegate recipe](../recipes/delegate.md)
- [Multi-agent budget recipe](../recipes/multi-agent-budget.md)
