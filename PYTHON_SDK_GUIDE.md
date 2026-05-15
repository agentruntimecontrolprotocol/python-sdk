# Python SDK Style Guide

> Opinionated, idiomatic rules for writing public Python SDKs.
> Optimized for Claude Code to read once and apply consistently.
> When a rule conflicts with a user request, follow the rule and note it.

---

## 0. Hard Limits (Enforce Always)

| Metric                  | Limit          | Note                                  |
| ----------------------- | -------------- | ------------------------------------- |
| Line length             | 80 aspirational, **100 hard** | Ruff: `line-length = 100`  |
| Function body length    | **30 lines**   | Excludes signature, docstring, blanks |
| File length             | **300 lines**  | Split by responsibility, not arbitrarily |
| Cyclomatic complexity   | **8**          | `ruff` rule `C901`                    |
| Function parameters     | **5**          | After 5, take a dataclass             |
| Nesting depth           | **3**          | Extract or invert                     |
| Public class methods    | **15**         | Above this = split the class          |

Any file or function exceeding these MUST be refactored, not exempted.

---

## 1. Public API Design

- Every public symbol is explicit. Use `__all__` in every module that
  contains anything public.
- `__init__.py` re-exports the package surface. Nothing else is public.
- Leading underscore = private. No exceptions. No `_helpers.py` with
  public functions inside.
- Keyword-only arguments for any function with more than 2 parameters.
  Use `*` separator.
- Never expose a boolean positional flag. Use `Enum`, `Literal`, or
  split into two functions.
- Return concrete types. Never `Any`. Never bare `dict` or `list`
  without parameters.
- Public signatures are immutable across minor versions. Adding
  optional kwargs is fine; reordering, renaming, or removing is not.
- Prefer factory functions or classmethods over constructors with
  many optional kwargs (`Client.from_env()`, `Client.from_config()`).

```python
# bad
def fetch(url, retry=True, timeout=30, verify=True):

# good
def fetch(
    url: str,
    *,
    retry: bool = True,
    timeout: float = 30.0,
    verify: bool = True,
) -> Response: ...
```

---

## 2. Type Hints (Non-Negotiable)

- 100% type coverage on public surface. `mypy --strict` passes.
- Ship `py.typed` marker file in the package root.
- Use built-in generics: `list[str]`, `dict[str, int]`, `tuple[int, ...]`.
- Use `X | None`, never `Optional[X]`. Never `Union[X, Y]`; use `X | Y`.
- Use `TYPE_CHECKING` guard for import-only-for-types.
- `Protocol` for duck-typed parameters (input contracts).
- `Literal["a", "b"]` for closed string sets; `Enum` for runtime sets.
- `TypeAlias` (PEP 613) for any type used in 2+ places.
- `Generic[T]` for containers; `ParamSpec` for decorators.
- Never `Any` without a `# type: ignore[<rule>]` comment justifying it.
- `cast()` only at trust boundaries (deserialization, FFI).

---

## 3. Data Models

- Value objects: `@dataclass(frozen=True, slots=True)`.
- I/O validation (HTTP bodies, config files): Pydantic v2. Never raw
  dicts at API boundaries.
- Internal records that need converters but not validation: `attrs`.
- Never use mutable defaults. `field(default_factory=list)`.
- Models do not have I/O methods. `.save()` belongs on a repository,
  not a model.

---

## 4. Errors

- Define one root exception per package: `class LibraryError(Exception)`.
- Subclass by category, then by specific failure:
  `NetworkError(LibraryError)` → `TimeoutError(NetworkError)`.
- Never `raise Exception(...)`. Never catch bare `Exception` except
  at top-level entry points (CLI, request handler).
- Always chain: `raise NewError(...) from original` or
  `raise NewError(...) from None` to suppress.
- Document `Raises:` in every public docstring.
- No control flow via exceptions. Exceptions = exceptional.
- Errors carry structured context: include the offending value, the
  operation attempted, and a remediation hint when possible.

---

## 5. Async

- Pick one: sync-only, async-only, or both. Document the choice.
- If both, generate one from the other (e.g., `unasync`) — don't
  maintain twice.
- Backend-agnostic async: prefer `anyio` over raw `asyncio` for
  library code (works under asyncio and trio).
- Provide `async with` for any resource. Never require the caller to
  remember to close.
- Cancel-safe: every `await` must leave the object in a valid state
  if cancelled.
- No blocking calls in async functions. `asyncio.to_thread` for
  unavoidable sync I/O.

---

## 6. Logging

- `logger = logging.getLogger(__name__)` at module top.
- Library packages add `logging.getLogger(__name__).addHandler(
  logging.NullHandler())` in `__init__.py`.
- **Never** `print()` in library code.
- Never call `logging.basicConfig()` or touch the root logger.
- Lazy formatting only: `logger.debug("user=%s", user)`, never
  `logger.debug(f"user={user}")` — the f-string evaluates even when
  the log level filters the message out.
- Levels: `DEBUG` = internal flow, `INFO` = lifecycle events,
  `WARNING` = recoverable issue, `ERROR` = operation failed,
  `CRITICAL` = process must terminate.

---

## 7. Dependencies

- Stdlib first. Reach for a third-party dep only when stdlib costs
  >50 lines or is materially worse.
- Pin lower bounds on runtime deps (`requests>=2.28`). Don't pin
  upper bounds unless you've actually hit a break.
- Extras for optional features: `pip install mylib[async,redis]`.
- No transitive surface leakage. If you use `httpx` internally, don't
  expose `httpx.Response` in your public API — wrap it.
- Vendor only as last resort, and document why.

---

## 8. Packaging

- `src/` layout. Always.
- `pyproject.toml` only. No `setup.py`, no `setup.cfg`.
- PEP 621 metadata. Single source of truth for version.
- Ship `py.typed` (empty file in package root).
- Build backend: `hatchling` (default), `setuptools` if you need
  C extensions.
- One package per repo (monorepos are a separate decision).

---

## 9. Imports

- Absolute imports in library code. Relative imports only inside
  tightly-coupled sibling modules of the same subpackage.
- No wildcard imports. Ever.
- Sorted by `ruff` (isort-compatible).
- Order: stdlib, third-party, first-party, local relative.
- `from __future__ import annotations` at the top of every module
  (faster startup, forward refs without quoting).

---

## 10. Naming

- `snake_case` for functions, variables, module names.
- `PascalCase` for classes and type aliases.
- `SCREAMING_SNAKE_CASE` for module-level constants.
- `_single_leading_underscore` for private.
- Never invent `__dunder__` names — that namespace is Python's.
- Names describe intent, not type. `users`, not `users_list`.
- Booleans read as predicates: `is_active`, `has_permission`,
  `should_retry`.
- No abbreviations in public API. `configuration` not `config` in
  type names; `cfg` is fine for local variables.

---

## 11. Documentation

- Google-style docstrings. Every public symbol.
- Sections: one-line summary, blank line, longer description,
  `Args:`, `Returns:`, `Raises:`, `Example:`.
- Examples are doctests where possible — they run in CI.
- README: install, 30-second quickstart, link to full docs.
- CHANGELOG.md follows [Keep a Changelog]. Updated in every PR
  that touches public surface.
- Public docs built with `mkdocs-material` or `sphinx` + autodoc.

```python
def parse_email(value: str) -> Email:
    """Parse a string into a validated Email.

    Args:
        value: The raw email string. Whitespace is stripped.

    Returns:
        A validated Email instance.

    Raises:
        InvalidEmailError: If the input does not match RFC 5322.

    Example:
        >>> parse_email("alice@example.com")
        Email('alice@example.com')
    """
```

---

## 12. Testing

- `pytest` only. No `unittest`, no `nose`.
- Test layout mirrors source: `src/pkg/foo.py` → `tests/test_foo.py`.
- 90%+ line coverage on public surface, 100% on parsers/validators.
- Fixtures over `setUp`/`tearDown`. Scope them tightly.
- Parametrize over copy-paste: `@pytest.mark.parametrize`.
- `hypothesis` for parsers, encoders, anything with an obvious
  round-trip property.
- Mock at the boundary (HTTP, filesystem). Never mock internals of
  the code under test.
- Snapshot tests (`syrupy`) for stable structured output only.
- No network in unit tests. Use `responses`, `respx`, or `vcrpy`.
- One behavior per test. Test name describes the behavior:
  `test_retry_gives_up_after_max_attempts`.

---

## 13. Tooling (Enforced in CI)

- `ruff` for lint + format. Replace black, isort, flake8.
- `mypy --strict` (or `pyright` strict).
- `pytest --cov --cov-fail-under=90`.
- `pre-commit` runs ruff + mypy + pytest --collect-only.
- Lock file (`uv.lock` or `poetry.lock`) committed for reproducibility.
- Build artifacts on every PR. Publish only from tagged commits.

Minimal `pyproject.toml` lint config:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "C90", "UP", "N", "SIM", "RUF"]
ignore = []

[tool.ruff.lint.mccabe]
max-complexity = 8

[tool.ruff.lint.pylint]
max-args = 5

[tool.mypy]
strict = true
warn_unreachable = true
```

---

## 14. Reducing Complexity (The Most Important Section)

Complexity is the source of all maintenance pain. These rules are
mechanical and non-negotiable.

### File-level

- **Max 300 lines per file.** If you're past it, the file has more
  than one responsibility. Split.
- One public class per file is the default. Group only when the
  classes are inseparable (e.g., builder + product).
- Module name matches its primary public symbol when possible.

### Function-level

- **Max 30 lines per function body.** Excludes signature, docstring,
  and blank lines. If you can't fit, extract.
- **Max 5 parameters.** Beyond 5, group them into a `@dataclass`.
- **Max nesting depth 3.** If you have `for { if { for { ... } } }`,
  invert with guard clauses or extract.
- **Max cyclomatic complexity 8.** Each branch (`if`, `elif`,
  `case`, `and`, `or`, `except`) adds 1. Above 8, decompose.
- Single Responsibility: a function does one thing. Its name is a
  verb phrase that describes that one thing. If you find yourself
  using "and" in the name, split it.

### Control flow

- **Early returns.** No `else` after `return`. Guard clauses at the
  top, happy path at the bottom.
- **No flag parameters.** `parse(strict=True)` and
  `parse(strict=False)` are two different functions. Make them so:
  `parse_strict()` and `parse_lenient()`.
- **Replace conditional dispatch with polymorphism or a dict.** A
  10-arm `if/elif` chain on a string is a `dict` of handlers.
- **Extract guard clauses ruthlessly.** `if not user: raise NotFound`
  is its own line, not nested in the body.

```python
# bad — nested, hard to scan
def process(user, request):
    if user is not None:
        if user.is_active:
            if request.is_valid():
                return handle(user, request)
            else:
                raise InvalidRequest
        else:
            raise InactiveUser
    else:
        raise UserNotFound

# good — guards first, happy path last
def process(user: User | None, request: Request) -> Result:
    if user is None:
        raise UserNotFound
    if not user.is_active:
        raise InactiveUser
    if not request.is_valid():
        raise InvalidRequest
    return handle(user, request)
```

### Data flow

- Prefer pure functions. Pure = same input → same output, no side
  effects.
- Push side effects (I/O, logging, mutation) to the edges. Pure core,
  impure shell.
- Immutability by default. Mutable state needs a reason.
- Don't reach into objects (`a.b.c.d`). Law of Demeter — talk to
  your neighbor.

### Composition

- Prefer composition over inheritance. Inherit only when there is a
  true is-a relationship and you control both sides.
- No more than 1 level of inheritance in your own code. Mixins are
  not exempt.
- Favor small protocols over abstract base classes for plug points.

### When you must violate a limit

You may not. Refactor instead. If genuinely impossible (generated
code, vendored upstream), add `# noqa: <rule>` with a comment
explaining why and a TODO with an owner.

---

## 15. Versioning & Compatibility

- Strict SemVer. Breaking change → major bump.
- Deprecate one minor version before removing. Use
  `warnings.warn(..., DeprecationWarning, stacklevel=2)`.
- Maintain CHANGELOG.md with sections: Added, Changed, Deprecated,
  Removed, Fixed, Security.
- Support the oldest Python that >5% of your users still run.
  Drop versions on major bumps only.
- CI matrix tests every supported Python on every PR.

---

## 16. Performance (Don't Optimize Prematurely)

- Correctness, clarity, complexity limits first. Performance second.
- Measure before optimizing. `pytest-benchmark`, `py-spy`, or
  `scalene`. Never guess.
- When you optimize, comment why and link the benchmark.
- Constant-time wins (avoid quadratic loops, use `set` for membership)
  are not optimization — they're correctness.

---

## 17. Security

- Never `eval`, `exec`, `pickle.loads` on untrusted input.
- Never log secrets. Add a `__repr__` to credential types that
  redacts.
- Validate at the boundary. Trust internal types.
- Use `secrets` module for tokens, never `random`.
- Pin TLS verification on by default. Make disabling it loud.
- Dependencies: `pip-audit` in CI.

---

## 18. Quick Reference: What Good Looks Like

```python
"""Email parsing for the foo package."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from foo.errors import InvalidEmailError

__all__ = ["Email", "parse_email"]

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class Email:
    """A validated email address."""

    value: str

    def __str__(self) -> str:
        return self.value


def parse_email(value: str) -> Email:
    """Parse a string into a validated Email.

    Args:
        value: Raw input. Stripped of surrounding whitespace.

    Returns:
        A validated Email.

    Raises:
        InvalidEmailError: If the input is not a valid email.
    """
    cleaned = value.strip()
    if not cleaned:
        raise InvalidEmailError("email is empty")
    if not _EMAIL_RE.match(cleaned):
        raise InvalidEmailError(f"invalid email: {cleaned!r}")
    return Email(cleaned)
```

That file is 30 lines of code. It hits every rule. Refactor toward
this shape.
