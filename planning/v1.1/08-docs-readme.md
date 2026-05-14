# 08 — Docs Tree, Frontmatter, README, Conformance

Scope: the Markdown the Python SDK ships for the shared docs site, plus
the wholly rewritten [`README.md`](../../README.md) and replacement of the
5-line [`CONFORMANCE.md`](../../CONFORMANCE.md) stub. The shared docs site
ingests plain Markdown from each SDK's `docs/` directory; this SDK ships
Markdown, not a generator. **No Sphinx config, no mkdocs.yml, no Read
the Docs config, no autodoc.** Pages link back to spec sections in
[`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md)
and forward-reference sibling planning artifacts
[`04-architecture.md`](04-architecture.md) (public API surface),
[`05-middleware.md`](05-middleware.md) (ASGI / aiohttp / OTel adapters),
[`06-examples.md`](06-examples.md) (the runnable examples), and
[`07-tests.md`](07-tests.md) (conformance harness). The TS doc analogs
are [`../../../typescript-sdk/README.md`](../../../typescript-sdk/README.md)
and [`../../../typescript-sdk/CONFORMANCE.md`](../../../typescript-sdk/CONFORMANCE.md);
the audit framing from
[`02-current-audit.md`](02-current-audit.md) §1 establishes that the
existing Python README is on draft-01 and gets fully replaced rather
than amended.

## 1. Docs tree under `docs/`

The shared site is single-rooted on each SDK's `docs/` directory and
sorts pages by frontmatter `order` within parent. The tree below is the
target post-merge layout; every file in it must exist before the site
build flips this SDK from "v1.0 draft" to "v1.1".

```
docs/
  00-overview.md                       What ARCP is, what this SDK is, links to spec + TS reference.
  01-quickstart.md                     Paired-MemoryTransport client + runtime in ~30 lines; mirrors README §4.
  02-concepts.md                       Envelopes, sessions, jobs, events, leases, delegation — same prose as README §5, citing spec §§5–10.
  03-features/                         One file per v1.1 feature flag from 01-spec-delta.md §3.
    capability-negotiation.md          §6.2 — features intersection, hasFeature/negotiatedFeatures surface.
    heartbeats.md                      §6.4 — feature flag `heartbeat`; ping/pong; HEARTBEAT_LOST.
    event-ack.md                       §6.5 — feature flag `ack`; session.ack; back-pressure status.
    list-jobs.md                       §6.6 — feature flag `list_jobs`; filters, cursor, request_id echo.
    subscribe.md                       §7.6 — feature flag `subscribe`; cross-session attach; replay seq rules.
    agent-versions.md                  §7.5 — feature flag `agent_versions`; `name@version`; AGENT_VERSION_NOT_AVAILABLE.
    lease-expires-at.md                §9.5 — feature flag `lease_expires_at`; ISO-UTC future; LEASE_EXPIRED.
    cost-budget.md                     §9.6 — feature flag `cost.budget`; per-currency counters; BUDGET_EXHAUSTED.
    progress.md                        §8.2 — feature flag `progress`; body schema + JobContext.progress.
    result-chunk.md                    §8.4 — feature flag `result_chunk`; streamResult writer + collectChunks reader.
  04-examples/                         One file per example from 06-examples.md (table mirrors TS examples/README.md).
    submit-and-stream.md
    delegate.md
    resume.md
    idempotent-retry.md
    lease-violation.md
    cancel.md
    stdio.md
    vendor-extensions.md
    custom-auth.md
    heartbeat.md
    ack-backpressure.md
    list-jobs.md
    subscribe.md
    agent-versions.md
    lease-expires-at.md
    cost-budget.md
    progress.md
    result-chunk.md
    tracing.md
    asgi.md
    aiohttp.md
  05-reference/                        One file per public API entry from 04-architecture.md §5.
    arcp-client.md                     `arcp.client.ARCPClient` — connect, submit, subscribe, listJobs, ack, hasFeature, close.
    arcp-runtime.md                    `arcp.runtime.ARCPRuntime` — accept, registerAgent, registerAgentVersion, setDefaultAgentVersion.
    transport.md                       `arcp.transport.Transport`, `MemoryTransport`, `pair_memory_transports`, `WebSocketTransport`, `StdioTransport`.
    job-context.md                     `arcp.runtime.JobContext` — log, status, metric, progress, result_chunk, streamResult, delegate, signal, budget.
    errors.md                          `arcp.errors.*` — the 15 typed exceptions and `ErrorCode` enum.
    middleware-asgi.md                 `arcp.middleware.asgi.arcp_asgi_app(runtime, *, allowed_hosts)` (Starlette / FastAPI / Litestar / Quart mount).
    middleware-aiohttp.md              `arcp.middleware.aiohttp.arcp_aiohttp_handler` + `serve_arcp_aiohttp` (aiohttp `web.Application` mount).
    middleware-otel.md                 `arcp.middleware.otel.with_tracing(inner, *, tracer)` (W3C trace context propagation + v1.1 span attrs).
  06-conformance.md                    The §-by-§ Implemented/Deferred matrix; replaces top-level CONFORMANCE.md.
```

Page-count invariants the site relies on:

- `03-features/` has exactly the nine entries in
  [`01-spec-delta.md`](01-spec-delta.md) §3 — one per feature flag in
  the spec §6.2 intersection vocabulary. `capability-negotiation.md` is
  the meta-page that describes the negotiation mechanism itself; it is
  not itself a flag.
- `05-reference/` has exactly one entry per public-symbol cluster in
  [`04-architecture.md`](04-architecture.md) §5. Adding a new public
  module is a docs change as well as a code change.
- `04-examples/` has one entry per example directory listed in
  [`06-examples.md`](06-examples.md) §1. The reconciled count is **21**
  (9 v1.0 core + 9 v1.1 + 3 host integrations); the audit's `§5`
  stub-figure of 18 is superseded — see
  [`10-synthesis.md` §2.1](10-synthesis.md) for the derivation.

## 2. Frontmatter schema

Identical across all SDKs in the workspace; the shared site parses YAML
frontmatter at the top of every file.

```yaml
---
title: "Heartbeats"
sdk: python
spec_sections: ["§6.4"]
order: 2
kind: feature
---
```

Field rules:

- `title` (string, REQUIRED) — page title; rendered as the H1, so the
  Markdown body MUST NOT also start with an H1.
- `sdk` (string, REQUIRED) — `python` for every file in this tree. The
  shared site uses this to scope navigation per SDK.
- `spec_sections` (array of strings) — REQUIRED and non-empty for
  `kind ∈ {feature, conformance}`; OPTIONAL elsewhere. Each entry is a
  literal spec section identifier (`"§6.4"`, `"§9.5"`); the site
  rewrites them to deep-links into `draft-arcp-02.1.md`. The
  `03-features/` rows must list every section their flag gates per the
  [`01-spec-delta.md`](01-spec-delta.md) §3 table.
- `order` (integer, REQUIRED) — sort key within parent directory.
  `00-overview.md` is `order: 0`; `01-quickstart.md` is `order: 1`;
  files in `03-features/` and `04-examples/` start at `order: 1` and
  increment in the alphabetic order shown above (the leading
  two-digit prefix on top-level files is for filesystem clarity only;
  the site sorts by `order`, not filename).
- `kind` (enum, REQUIRED) — one of `overview | guide | feature |
  example | reference | conformance`. The mapping is mechanical:
  - `00-overview.md` → `overview`
  - `01-quickstart.md`, `02-concepts.md` → `guide`
  - `03-features/*.md` → `feature`
  - `04-examples/*.md` → `example`
  - `05-reference/*.md` → `reference`
  - `06-conformance.md` → `conformance`

Everything after the frontmatter is plain CommonMark + GFM tables. The
shared site does not accept HTML, nested admonition syntax (no
`:::note`), rST directives, MyST extensions, or Sphinx roles. Code
fences MUST declare a language (`python`, `json`, `text`). Links use
repo-relative paths (`../../../spec/docs/draft-arcp-02.1.md#section-64`,
`../05-reference/arcp-client.md`) so the site renderer can rewrite them
per environment.

## 3. Per-feature page template

Every `03-features/<flag>.md` page has the same six-section shape so
the site's per-flag navigation widget can render them uniformly and so
the conformance audit in [`07-tests.md`](07-tests.md) can grep them
deterministically.

```
---
title: "<Human title>"
sdk: python
spec_sections: ["§X.Y"]
order: N
kind: feature
---

## What it is

One paragraph. State the wire surface change (verbs / payload fields /
event kinds), the v1.0 fallback behaviour, and the side of the wire that
emits it (client / runtime / either).

## Feature flag

The exact string sent on `session.hello.payload.capabilities.features`
and echoed on `session.welcome.payload.capabilities.features`.
Copy-paste from 01-spec-delta.md §3.

## Wire example

A fenced ```json``` block lifted verbatim from the spec section for the
feature (e.g. the `session.ping` / `session.pong` block from §6.4). No
abbreviation; no edits beyond removing surrounding prose.

## Python API

The exact public signature(s) from 04-architecture.md §5 (e.g.
`ARCPClient.list_jobs(filter: ListJobsFilter | None = None, *, limit:
int | None = None, cursor: str | None = None) -> ListJobsResult`).
Include the imports the user needs and link to `../05-reference/<page>.md`.

## Failure modes

Bulleted list of error codes from spec §12 that can surface on this
feature (`INVALID_REQUEST` on malformed payload, `BUDGET_EXHAUSTED` on
zero counter, etc.), each mapped to its Python exception type in
`arcp.errors`. Cross-reference 01-spec-delta.md §2 for the v1.1 codes.

## See also

Link to the matching example under `../04-examples/<name>.md` and to
the spec section.
```

Per-flag fills:

- `heartbeats.md` — flag `heartbeat`, spec §6.4, Python:
  `SessionContext.start_heartbeat` (runtime side), `ARCPClient` ping
  reply path; failures: `HEARTBEAT_LOST`.
- `event-ack.md` — flag `ack`, spec §6.5, Python:
  `ARCPClient.ack(seq)` and `ARCPClient(auto_ack=...)`; failures:
  back-pressure `status` event (no error code per se).
- `list-jobs.md` — flag `list_jobs`, spec §6.6, Python:
  `ARCPClient.list_jobs(...)`; failures: `INVALID_REQUEST` on
  malformed filter; same-principal default scope.
- `subscribe.md` — flag `subscribe`, spec §7.6, Python:
  `ARCPClient.subscribe(job_id, history=, from_event_seq=)`; failures:
  `JOB_NOT_FOUND`, `PERMISSION_DENIED`.
- `agent-versions.md` — flag `agent_versions`, spec §7.5 + §13.7,
  Python: `ARCPRuntime.register_agent_version`,
  `set_default_agent_version`; failures:
  `AGENT_VERSION_NOT_AVAILABLE` (`session.error`, not `job.error`).
- `lease-expires-at.md` — flag `lease_expires_at`, spec §9.5, Python:
  `LeaseConstraints(expires_at=...)` on submit; failures:
  `INVALID_REQUEST` (past / non-UTC), `LEASE_EXPIRED`.
- `cost-budget.md` — flag `cost.budget`, spec §9.6 (+ §9.4 subset
  rule), Python: `lease_request={"cost.budget": ["USD:5.00"]}`,
  `JobContext.budget` snapshot; failures: `BUDGET_EXHAUSTED`,
  `INVALID_REQUEST` on negative metric.
- `progress.md` — flag `progress`, spec §8.2.1, Python:
  `JobContext.progress(current, total=, units=, message=)`; failures:
  `INVALID_REQUEST` on negative `current`.
- `result-chunk.md` — flag `result_chunk`, spec §8.4, Python:
  `JobContext.stream_result()` writer + `JobHandle.collect_chunks()`
  reader; failures: `INVALID_REQUEST` if inline `result` and
  `result_chunk` are mixed; `INTERNAL_ERROR` on chunk-size cap from
  spec §14.

## 4. Reference page shape

`05-reference/*.md` pages are hand-written from
[`04-architecture.md`](04-architecture.md) §5. The site does NOT
autogenerate from source; an autodoc pass would entangle the docs with
import order, lazy re-exports, and `__init__` side effects and would
diverge from the TS reference, which is hand-written for the same
reason. Each reference page has:

1. Frontmatter (`kind: reference`, no `spec_sections` required).
2. One-paragraph purpose, naming the module path (e.g. `arcp.client`).
3. A "Symbols" table: `Name | Kind | Summary`.
4. Per symbol, an H2 with the exact signature in a `python` code fence,
   one paragraph describing semantics, and a "Raises" block listing the
   exceptions from `arcp.errors` it can surface.
5. A "See also" block linking to the relevant `03-features/*.md` and
   the spec section.

No prose summary should restate code; either the signature carries the
information or it goes in the paragraph. No "Note:" admonitions; if it
matters, it goes in the paragraph.

## 5. README outline (rewrite of `python-sdk/README.md`)

Mirrors [`../../../typescript-sdk/README.md`](../../../typescript-sdk/README.md)
section-for-section, with Python conventions. The current
[`../../README.md`](../../README.md) is on draft-01
(`PROTOCOL_VERSION = "1.0"`, `Envelope.timestamp`, etc., per
[`02-current-audit.md`](02-current-audit.md) §1) and is replaced
wholesale.

Sections, in order:

1. **Title + badges.** Header is `# ARCP — Agent Runtime Control
   Protocol (Python reference)`. Badges, repo-relative-linked: License
   (Apache-2.0), Python version (`≥3.11` per
   [`03-libraries.md`](03-libraries.md) §1 decisions table), ARCP
   version (`v1.1`, linking
   [`../../../spec/docs/draft-arcp-02.1.md`](../../../spec/docs/draft-arcp-02.1.md)).
2. **What this is (one paragraph).** "Reference implementation of ARCP
   v1.1 for Python. Backward-compatible with v1.0 peers via the
   capability-negotiation surface in spec §6.2." Mention that v1.1 is
   additive over v1.0 ([`01-spec-delta.md`](01-spec-delta.md) §1) and
   that this SDK is one of the workspace's eleven implementations
   tracked in the per-SDK conformance pages. No marketing adjectives.
3. **Install.** Show `uv add arcp` first, `pip install arcp` second
   (matches [`03-libraries.md`](03-libraries.md) §15 package-manager
   pick). Then the subpackage table. Unlike TS — where each subpackage
   is a distinct npm package — the Python SDK is **one distribution**
   named `arcp`. The table's columns are subpackages of that one
   distribution:

   | Subpackage                  | What it contains                                                                            |
   | --------------------------- | ------------------------------------------------------------------------------------------- |
   | `arcp`                      | Top-level re-exports (`ARCPClient`, `ARCPRuntime`, `MemoryTransport`, `pair_memory_transports`, errors, version constants). |
   | `arcp.client`               | `ARCPClient`, `JobHandle`, `ListJobsResult`, `SubscribeHandle`.                             |
   | `arcp.runtime`              | `ARCPRuntime`, `JobContext`, `SessionContext`, agent registry, lease helpers.               |
   | `arcp.transport`            | `Transport` protocol, `MemoryTransport`, `WebSocketTransport`, `StdioTransport`.            |
   | `arcp.middleware.asgi`      | `serve_arcp(app, ...)` ASGI mount for Starlette / FastAPI / generic.                        |
   | `arcp.middleware.aiohttp`   | `attach_arcp(app, ...)` for `aiohttp.web.Application`.                                      |
   | `arcp.middleware.otel`      | `instrument(runtime)` — W3C trace context propagation + v1.1 span attrs (§11).              |

   Restate after the table: "All of the above ship in one wheel; no
   à-la-carte install."
4. **Quickstart.** Full runnable client + runtime in approximately 30
   lines, all imports concrete (no `…`), using `pair_memory_transports()`
   from `arcp.transport` — the Python equivalent of TS
   `pairMemoryTransports`. The code uses `asyncio.run` and an
   `asyncio.TaskGroup` for the runtime accept loop. Reference
   [`../../examples/submit_and_stream/`](../../examples/submit_and_stream/)
   for the runnable two-process version. Exit code 0 is part of the
   contract: if the script does not terminate normally, the README
   block is wrong. Mark imports complete; mark elisions inside the
   agent body with `# elided: <what's missing>` per the voice rules
   in §7 below.
5. **Core concepts.** Lift the TS README's tables wholesale where the
   wire is identical — the envelope table (§5), the sessions handshake
   diagram (§6), the jobs lifecycle (§7), the event-kinds table (§8),
   the lease grammar (§9), delegation (§10). Replace TS code spans
   with Python module paths (`@arcp/core` → `arcp.client`, etc.). The
   only Python prose is in two places: (a) where the asyncio idiom
   differs from JS — call out `CancelledError` propagation in the
   cancellation paragraph per
   [`02-current-audit.md`](02-current-audit.md) §4; (b) where Python's
   type model differs — note `discriminated union via pydantic on
   payload.kind` once, in §8.
6. **v1.1 additions.** A single paragraph listing the nine negotiated
   features with `code`-spans, each linking to its
   `docs/03-features/<flag>.md` page: `heartbeat`, `ack`, `list_jobs`,
   `subscribe`, `agent_versions`, `lease_expires_at`, `cost.budget`,
   `progress`, `result_chunk`. State the intersection rule from spec
   §6.2 in one sentence and link to
   `docs/03-features/capability-negotiation.md`.
7. **Running the runtime.** Two subsections:
   - **Programmatic.** `ARCPRuntime` instantiation with
     `StaticBearerVerifier` from `arcp.auth.bearer` (interface salvaged
     per [`02-current-audit.md`](02-current-audit.md) §2),
     `register_agent`, and either `serve_websocket(host, port,
     on_transport=runtime.accept)` from `arcp.transport.websocket` or
     mounting `arcp.middleware.asgi.arcp_asgi_app(runtime,
     allowed_hosts=[...])` at `/arcp` in any ASGI app.
   - **CLI.** Three commands matching the TS surface in
     [`../../../typescript-sdk/README.md`](../../../typescript-sdk/README.md)
     §"CLI":

     ```sh
     uv run arcp serve   --host 127.0.0.1 --port 7777 \
                         --token tok --principal me@example.com
     uv run arcp submit  --url ws://127.0.0.1:7777 \
                         --token tok --agent my-agent --input '{"hi":1}'
     uv run arcp replay  --db arcp.db --session sess_XYZ --after-seq 0
     ```

     Note `--transport stdio` for child-process mode (spec §4.2).
     Commands are implemented in `arcp/cli.py` (Click, per
     [`03-libraries.md`](03-libraries.md) §12).
8. **Writing clients.** Show the canonical async-context-manager
   pattern in ~20 lines:

   ```python
   async with ARCPClient.connect(
       WebSocketTransport.connect("wss://runtime.example.com/arcp"),
       client={"name": "my-client", "version": "1.0.0"},
       auth_scheme="bearer",
       token=os.environ["TOKEN"],
   ) as client:
       handle = await client.submit(
           agent="weekly-report",
           input={"week": "2026-W19"},
           lease={"net.fetch": ["s3://example/**"]},
           idempotency_key="weekly-report-2026-W19",
       )
       async for event in handle.events():
           # elided: render event to stdout / UI
           pass
       result = await handle.done
   ```

   Note: `__aenter__` performs the handshake and returns the connected
   client; `__aexit__` sends `session.bye` (spec §6.7) and closes the
   transport. Cancellation propagates `asyncio.CancelledError` into
   `handle.done` per [`02-current-audit.md`](02-current-audit.md) §4.
9. **Conformance.** One paragraph linking to
   [`docs/06-conformance.md`](../../docs/06-conformance.md) and giving
   the v1.1 status summary (numbers come from the conformance matrix
   itself; this paragraph is regenerated when that page changes).
10. **Examples.** Abbreviated three-table block (v1.0 core, v1.1
    features, host integrations) lifted from
    [`06-examples.md`](06-examples.md), each row a `code`-span linking
    to `docs/04-examples/<name>.md`. No prose around the tables.
11. **Development.** Exactly four commands from
    [`03-libraries.md`](03-libraries.md):

    ```sh
    uv sync                # install incl. dev extras
    uv run pytest          # tests/
    uv run ruff check      # lint + format check
    uv run pyright         # strict type check
    ```

    No CI badges, no contributing-guide link in this section (the
    `CONTRIBUTING.md`, if any, is referenced from the License section
    below, not here).
12. **License.** `Apache-2.0`, link to
    [`../../LICENSE`](../../LICENSE).

The README does **not** include a "Future work" / "Roadmap" / "What's
next" section. Roadmap items belong in spec issues, not in the
shipping README ([§6 hard rules](#6-hard-rules)).

## 6. Conformance page (`docs/06-conformance.md`)

Mirrors [`../../../typescript-sdk/CONFORMANCE.md`](../../../typescript-sdk/CONFORMANCE.md)
row-by-row with the same section grouping (§4 Transport, §5 Wire
Format, §6 Sessions, §7 Jobs, §8 Job Events, §9 Leases, §10
Delegation, §11 Trace Propagation, §12 Error Taxonomy, §13 Examples,
§14 Security, §15 IANA, then the v1.1 additions block — §6.2
Capabilities, §6.4–§6.6, §7.5–§7.6, §8.2 / §8.4, §9.4–§9.6, §11
attrs, §12 v1.1 codes). Replaces the 5-line stub at
[`../../CONFORMANCE.md`](../../CONFORMANCE.md) — that file becomes a
two-line pointer to `docs/06-conformance.md` so old links continue
resolving, or is deleted; either is acceptable but only one survives.

Frontmatter:

```yaml
---
title: "Conformance — ARCP v1.1 (Python)"
sdk: python
spec_sections: ["§4", "§5", "§6", "§7", "§8", "§9", "§10", "§11", "§12", "§13", "§14", "§15"]
order: 6
kind: conformance
---
```

Row shape, applied uniformly to every table on the page:

| Column        | Content                                                                                                       |
| ------------- | ------------------------------------------------------------------------------------------------------------- |
| `Requirement` | The normative quote or paraphrase from the spec, prefixed with the subsection (e.g. `§6.4 \`session.ping\``). |
| `Status`      | `Implemented` or `Deferred`. Two values only.                                                                 |
| `Location`    | Citation in the project source tree.                                                                          |

Status taxonomy:

- `Implemented` — the requirement is present in `src/arcp/` and tested
  by `tests/conformance/` per [`07-tests.md`](07-tests.md).
- `Deferred` — intentionally not shipped in this release, with the
  reason in the row's `Requirement` cell or in a footnote table
  matching the "Intentional deferrals" block at the bottom of the TS
  conformance page.
- No `Partial`. Partial implementations are bugs to be tracked in
  GitHub issues, not states in the conformance matrix. The matrix is
  a release gate; a row is `Implemented` or it is `Deferred`. This
  rule is the conformance page's single load-bearing invariant — it
  exists so the parametrized rows in `tests/conformance/` from
  [`07-tests.md`](07-tests.md) have an unambiguous expectation per
  row.

Citation format, applied uniformly across every row:

```
arcp/client/client.py:L142
arcp/runtime/server.py:L317
arcp/runtime/lease.py:L88
```

The form is `<repo-relative-path>:L<line>`, where `<repo-relative-path>`
starts at `src/arcp/` (no leading `src/` prefix — the docs site
strips it for display, and the conformance test in
[`07-tests.md`](07-tests.md) Phase 7 derives the path with a fixed
`src/` prefix). When a row needs more than one citation, separate with
` ; ` (semicolon + space) within the same cell. The dotted-module form
(`arcp.runtime.server:L317`) is **not** used — it is ambiguous between
modules and packages and breaks line-number jumping in the GitHub
viewer.

This page is the source of truth for the parametrized
`tests/conformance/test_conformance_matrix.py` rows in
[`07-tests.md`](07-tests.md) §X. Each `Implemented` row must have a
corresponding test that asserts the cited line exists and matches a
regex; the test will fail when the line moves and either the citation
or the test is wrong — that is the wiring that keeps the matrix
honest.

The page additionally ships an "Intentional deferrals" table at the
bottom mirroring the TS page's, with Python-specific entries:

- Persistent idempotency store — in-memory only (per
  [`02-current-audit.md`](02-current-audit.md) §2 row `store/eventlog.py`).
- Client-side proactive heartbeat ping — same status as TS (replies
  only; deferred symmetric pinger).
- Sandboxed lease enforcement — `validate_lease_op` is the SDK seam;
  agents call it (mirrors TS).
- `msgspec` for hot-path validation — deferred per
  [`03-libraries.md`](03-libraries.md) §1 (pydantic v2 picked uniformly).

## 7. Voice rules

These rules apply to every Markdown file in `docs/`, to
[`README.md`](../../README.md), and to
[`CONFORMANCE.md`](../../CONFORMANCE.md). They are also the criteria
[`07-tests.md`](07-tests.md)'s docs-lint job (`ruff` is for Python; a
separate `lychee` + `markdownlint` pass covers Markdown) checks before
merge.

- **Terse.** One paragraph per idea; no preamble; no recap. If a sentence
  exists, it's because removing it breaks the page. The "Core
  concepts" section of the README is a worked example: each
  subsection is two sentences plus a table.
- **No marketing tone, no emojis.** None. Not in headers, not in lists,
  not in code comments inside examples.
- **No second-person exhortation.** Banned words: `simply`, `just`,
  `easily`, "you can". Allowed: imperative direct address inside
  step-by-step examples ("Set the bearer token…"); declarative third
  person elsewhere.
- **Banned adjectives.** `leverage`, `robust`, `scalable`,
  `performant`, `powerful`, `modern`, `easy to use`,
  `developer-friendly`, `best-in-class`. The docs-lint pass greps for
  these and fails on hit.
- **Runnable code.** Every fenced block tagged `python` must be
  runnable as-is with the imports shown. No `…`, no abbreviated
  imports, no fictional modules. When abbreviation is unavoidable
  inside a code block, mark the elision explicitly with a comment of
  the exact form `# elided: <what's missing>` (e.g.,
  `# elided: render event to stdout / UI`). The lint pass enforces
  this form.
- **Cross-links are repo-relative paths.** Inside `docs/` use
  `../../../spec/docs/draft-arcp-02.1.md` (relative from
  `docs/03-features/`), `../05-reference/arcp-client.md`,
  `../04-examples/heartbeat.md`. The shared site rewrites these for
  the hosted environment; absolute URLs to `github.com` are reserved
  for the spec PDF link in the page footer (one place only).
- **Cite spec, TS path, Python module path on every recommendation.**
  When the docs say "the client must respect the intersection rule",
  the sentence ends with `(spec §6.2; TS
  ../../../typescript-sdk/packages/core/src/version.ts:intersectFeatures;
  Python arcp.version:intersect_features)`. This is the
  three-pointer pattern used throughout the planning docs and
  inherited verbatim into the shipping docs.

## 8. Hard rules

- **No Sphinx, no mkdocs, no Read the Docs.** Plain Markdown only.
  No `conf.py`, no `mkdocs.yml`, no `_static/` or `_templates/`. The
  shared docs site is the only renderer; a per-SDK generator would
  fork the rendering matrix.
- **No autogenerated API reference.** Reference pages under
  `05-reference/` are hand-written from
  [`04-architecture.md`](04-architecture.md) §5's signatures. Drift
  between the architecture document and the reference pages is a
  release-blocking bug, not a process to automate around.
- **No "Future work" / "Roadmap" / "What's next" section in the
  README** or anywhere else under `docs/`. Roadmap items live in spec
  issues and per-feature GitHub issues; they do not ship in the
  release artifact.
- **Frontmatter is mandatory.** A file with missing or malformed
  frontmatter is rejected by the shared site's ingestion step. The
  CI lint pass in [`07-tests.md`](07-tests.md) enforces the schema
  in §2 of this doc.
- **No HTML inside Markdown.** No `<details>`, no `<sub>`, no inline
  `<a>`. The site renderer strips HTML, and the diff between rendered
  and intended output is the failure mode this rule exists to prevent.

## 9. Cross-references for downstream phases

- [`04-architecture.md`](04-architecture.md) §5 produces the public-API
  list that drives every file under `05-reference/`. Adding a public
  symbol there obliges a new reference page here.
- [`05-middleware.md`](05-middleware.md) defines the three adapter
  modules (`arcp.middleware.asgi`, `arcp.middleware.aiohttp`,
  `arcp.middleware.otel`) named in the README install table (§5 above)
  and in `05-reference/middleware-*.md`.
- [`06-examples.md`](06-examples.md) defines the example directory
  list, which seeds `04-examples/`'s file set 1:1.
- [`07-tests.md`](07-tests.md) consumes
  [`docs/06-conformance.md`](../../docs/06-conformance.md) as a
  parametrized fixture; every `Implemented` row becomes a test row.
- [`09-diagrams.md`](09-diagrams.md) supplies the architecture and
  sequence diagrams referenced from `02-concepts.md` and the
  per-feature pages. `.dot` source plus rendered light/dark SVG pairs
  ship under [`docs/diagrams/`](../../docs/diagrams/) (not
  `docs/assets/` — see `09-diagrams.md` §"Anchors") and are linked via
  GitHub's `<picture>` element with `prefers-color-scheme`; Mermaid is
  not used (the shared site does not run Mermaid).
- [`10-synthesis.md`](10-synthesis.md) records that the README rewrite
  and the conformance page replacement are Phase-8 deliverables, not
  follow-ups to the v1.0 realign in
  [`02-current-audit.md`](02-current-audit.md).
