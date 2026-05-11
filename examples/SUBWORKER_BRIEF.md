# Brief for translating ARCP examples to other SDKs

Canonical source: `/Users/nficano/code/arpc/python-sdk/examples/`.
Read those 14 example directories first — they're the spec for what
to produce.

## The fourteen examples

Each demonstrates one ARCP primitive from RFC-0001 v2. All come
from the Python tree; replicate the **shape** of each `main.*`
faithfully in the target language.

| Name | Primitive | Spec |
|---|---|---|
| `subscriptions` | Observer subscriptions, three sinks, three filters | §5, §13 |
| `leases` | Lease-gated shell agent | §15.4–§15.5 |
| `lease_revocation` | Per-table leases + `lease.revoked`/`lease.extended` mid-flight | §15.5 |
| `permission_challenge` | Two-party permission challenge with veto | §15.4, §6.4 |
| `delegation` | `agent.delegate` fan-out + JobMux | §14, §6.4 |
| `handoff` | `agent.handoff` with transcript packed as artifact | §14, §16, §8.3 |
| `heartbeats` | Worker federation; heartbeat loss reroutes via `idempotency_key` | §10.3, §6.4 |
| `capability_negotiation` | Capability-driven peer routing + cost rollups | §7, §17.3.1, §18.3 |
| `resumability` | **Real crash and resume** via `os._exit`/equivalent + `resume` envelope | §10, §19, §6.4 |
| `reasoning_streams` | `kind: thought` streams + peer mirror that delegates critiques back | §11.4, §13, §14 |
| `extensions` | Custom `arcpx.sdr.*.v1` extension namespace; unknown-message handling | §21 |
| `human_input` | `human.input.request` fanned across phone/email/Slack; first-wins | §12 |
| `cancellation` | Cooperative `cancel` (terminate) vs `interrupt` (pause and ask) | §10.4–§10.5 |
| `mcp` | ARCP runtime fronting an MCP server: `tool.invoke` → MCP `call_tool` | §20 |

## Conventions (verbatim from the Python set)

1. **One main file** per example carrying all the protocol-relevant
   code. Helper stubs (LLM calls, framework wiring, hardware) live
   in tiny named files (`agents.*`, `steps.*`, `synth.*`,
   `cheap.*`, `work.*`, `channels.*`, `sql.*`, `upstream.*`) and
   `raise NotImplementedError` (or language equivalent).
2. **`ARCPClient(...)`-style elision.** Setup boilerplate
   (transport URL, identity, auth blocks) is replaced with a
   one-line `...` placeholder + comment. The protocol code is what
   the reader sees.
3. **Illustrative, not runnable.** Imports name the SDK's public
   types as if it were already published. Don't compile-check end-
   to-end; pattern-match on `arcp` SDK shape from your language's
   actual `src/`.
4. **Envelopes match RFC-0001 v2 exactly.** Field names, message
   types, error codes are stable across languages. Custom types
   follow §21.1 `arcpx.<domain>.<name>.v<n>` naming.
5. **Per-example README.md** with: one-paragraph TL;DR, "Before
   ARCP" section, "With ARCP" code snippet, ARCP primitives list,
   file tour, variations.
6. **Tight.** Each main file is 50–180 LOC. If a translation feels
   like it needs more, you're fighting the language's idioms or
   over-eliding the wrong thing.

## What NOT to do

- Don't reimplement framework helpers (LangGraph, AutoGen, CrewAI).
  Stub them. The Python originals do this.
- Don't add a config file unless your language strongly idiomatic-
  ally requires one — Python killed `config.py` partway through.
- Don't number the directories (`01_…`). Match the Python primitive
  names exactly.
- Don't expand `ARCPClient(...)` into 30 lines of transport
  construction. The whole point is keeping the protocol visible.

## Per-language idioms to honor

- **Cargo / Rust**: each example as `examples/<name>.rs` (single
  file `cargo run --example <name>` form) when ≤180 LOC; otherwise
  a directory with `main.rs` + `mod` files. Keep `Cargo.toml`
  declarations under `[[example]]`.
- **Go**: `examples/<name>/main.go` per example. Stubs as separate
  `.go` files in the same package. `go.mod` already exists at SDK
  root; no per-example module.
- **Java/Kotlin (Gradle)**: each example is a class under
  `examples/src/main/<java|kotlin>/com/arcp/examples/<name>/`. One
  `Main.<ext>` per example; stubs as siblings. The `examples/`
  Gradle subproject builds them all.
- **TypeScript**: `examples/<name>.ts` for ≤180 LOC; otherwise a
  directory with `main.ts` + sibling stub modules.
- **C#/F#**: each example as `samples/<Name>/` with the project
  file (`<Name>.csproj` or `.fsproj`) and a `Program.cs`/`.fs` plus
  stubs.
- **PHP**: `samples/<name>/main.php` + sibling `.php` stubs. Use
  PSR-4 style.
- **Ruby**: `samples/<name>/main.rb` + sibling `.rb` stubs.
- **Swift**: `Samples/<Name>/Package.swift` + `Sources/<Name>/main.swift`
  + sibling `.swift` stubs.

## Equivalent tools when "no native equivalent"

The Python examples use Python-only frameworks. Substitute:

- LangGraph / LangChain → most languages: stub it.
- AutoGen → stub.
- CrewAI → stub.
- Pydantic AI → stub. For Java/Kotlin: hint at picocli or jackson.
- LiteLLM → most languages have nothing; stub. TS could mention
  `ai` or `vercel-ai-sdk`; Go nothing native; Rust nothing native.
- Anthropic SDK → use the official one if available
  (`@anthropic-ai/sdk`, `anthropic-sdk-go`, `anthropic-java-sdk`,
  `anthropic-rs`); else stub.
- LlamaIndex → most languages: stub.
- SoapySDR → stub everywhere; SDR is a niche.
- MCP SDK → `@modelcontextprotocol/sdk` (TS), `modelcontextprotocol`
  (Java/Kotlin), `modelcontextprotocol-go`, `modelcontextprotocol-rb`,
  `mcp-rs`; if no stable lib in a language, stub the import path
  and add a `// TODO: replace with vendored bridge` note.
- aiosqlite → SQLite client native to each language.
- structlog → each language's idiomatic logger.
- OpenTelemetry → has bindings in every language; reference them.

## Output checklist per example

Per `<example>` directory under your SDK's idiomatic samples folder:

- One main file (the protocol code).
- 0–2 stub modules (`agents.*`, etc.) when the Python original has
  them.
- `README.md` mirroring the Python README structure.
- Per-language deps manifest if your SDK doesn't have one
  centrally:
  - Rust: `[[example]]` entry in workspace `Cargo.toml`.
  - Java/Kotlin: dependencies declared in the
    `examples/build.gradle.kts` once.
  - PHP: `composer.json` if the example needs deps not in root.
  - Ruby: `Gemfile` if needed.
  - TS: dependencies declared in the SDK's root `package.json`.
  - Swift: each example's `Package.swift`.

## Verification

After writing your 14 examples, run the SDK's lint / format
toolchain (`cargo fmt && cargo clippy`, `gofmt && go vet`,
`./gradlew spotlessApply`, `npx biome check`, `dotnet format`,
`swift format`, `php-cs-fixer`, `rubocop`) on the new files. Fix
warnings unless they're substantive.

Update the SDK's top-level samples/examples README index to list
the 14 new examples by primitive name + one-line description.
