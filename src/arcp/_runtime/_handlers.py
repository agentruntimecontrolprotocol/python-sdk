"""Envelope dispatch handlers (session.* and job.* verbs)."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from .._envelope import Envelope
from .._errors import (
    DuplicateKeyError,
    InternalError,
    InvalidRequestError,
    JobNotFoundError,
    PermissionDeniedError,
)
from .._messages.execution import (
    CredentialConstraintsPayload,
    CredentialPayload,
    JobAcceptedPayload,
    JobCancelledPayload,
    JobCancelPayload,
    JobSubmitPayload,
    JobSubscribedPayload,
    JobSubscribePayload,
    JobUnsubscribePayload,
)
from .._messages.session import (
    SessionAckPayload,
    SessionClosedPayload,
    SessionClosePayload,
    SessionPingPayload,
    SessionPongPayload,
)
from .._transport.base import TransportClosed
from .._time import now_iso_z as _now_iso
from .._ulid import new_envelope_id, new_job_id
from .credentials import Credential, JobCredentialContext
from .job import Job
from .lease import (
    assert_lease_subset,
    echo_budget_for_accept,
    initial_budget_from_lease,
    validate_lease_constraints,
    validate_lease_shape,
)

if TYPE_CHECKING:
    from .server import ARCPRuntime
    from .session import SessionContext


async def handle_ping(_runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    ping = SessionPingPayload.model_validate(env.payload)
    pong = SessionPongPayload(ping_nonce=ping.nonce, received_at=_now_iso())
    out = Envelope(
        id=new_envelope_id(),
        type="session.pong",
        session_id=ctx.session_id,
        payload=pong.model_dump(mode="json"),
    )
    ctx.stamp_and_enqueue(out)


async def handle_ack(runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    if not ctx.has_feature("ack"):
        return
    ack = SessionAckPayload.model_validate(env.payload)
    ctx.record_ack(ack.last_processed_seq)
    # Await directly so (a) exceptions propagate to the dispatch loop instead
    # of being lost on an orphan task and (b) successive acks for the same
    # session are serialized — preventing concurrent DELETEs from racing.
    try:
        await runtime.event_log.release_through(ctx.session_id, ack.last_processed_seq)
    except Exception:
        # Surface but do not kill the session: a slow/locked disk should
        # not break ack handling for unrelated future envelopes.
        runtime.logger.exception(
            "event_log_release_failed",
            session_id=ctx.session_id,
            through_seq=ack.last_processed_seq,
        )


async def handle_close(_runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    # §6.7: acknowledge `session.close` with `session.closed`, then tear the
    # transport down. In-flight jobs keep running and remain resumable. The
    # ack is sent directly (not via the write pump) so it is flushed before
    # the transport closes.
    close = SessionClosePayload.model_validate(env.payload)
    closed = Envelope(
        id=new_envelope_id(),
        type="session.closed",
        session_id=ctx.session_id,
        payload=SessionClosedPayload(reason=close.reason).model_dump(
            mode="json", exclude_none=True
        ),
    )
    with contextlib.suppress(TransportClosed):
        await ctx.transport.send(closed.to_wire())
    await ctx.transport.close()


from ._handler_list_jobs import handle_list_jobs  # noqa: E402


async def handle_submit(runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    submit = JobSubmitPayload.model_validate(env.payload)
    validate_lease_shape(submit.lease_request)
    validate_lease_constraints(submit.lease_constraints)
    if submit.idempotency_key is None:
        await _build_and_launch(runtime, ctx, env, submit)
        return
    # §7.2: serialize check-and-store for a given (principal, key) across the
    # awaiting job build (e.g. credential issuance) so two concurrent same-key
    # submits — which a single principal may make over multiple sessions —
    # cannot both miss the store and create duplicate jobs.
    async with runtime.idempotency.lock_for(ctx.principal, submit.idempotency_key):
        if _replay_idempotent(runtime, ctx, env, submit):
            return
        await _build_and_launch(runtime, ctx, env, submit)


async def _build_and_launch(
    runtime: ARCPRuntime, ctx: SessionContext, env: Envelope, submit: JobSubmitPayload
) -> None:
    _enforce_delegation_subset(runtime, ctx, submit)
    agent_fn, name, version = runtime._resolve_agent(submit.agent)
    job, accept_env = await _build_job_and_accept(runtime, ctx, env, submit, name, version)
    if submit.idempotency_key is not None:
        runtime.idempotency.put(
            ctx.principal,
            submit.idempotency_key,
            job_id=job.job_id,
            accepted_envelope=accept_env.to_wire(),
            submit_fingerprint=runtime.idempotency.fingerprint(env.payload),
        )
    ctx.stamp_and_enqueue(accept_env)
    task = asyncio.create_task(
        runtime._run_job(job, agent_fn, submit.input, max_runtime_sec=submit.max_runtime_sec)
    )
    runtime._job_tasks[job.job_id] = task


def _enforce_delegation_subset(
    runtime: ARCPRuntime, ctx: SessionContext, submit: JobSubmitPayload
) -> None:
    """§9.4/§10: a delegated job's lease must be a strict subset of its parent.

    When `parent_job_id` is set, the child's lease, budget, and expiry are
    checked against the parent's (which the requester must own). Authority that
    would exceed the parent is rejected with `LEASE_SUBSET_VIOLATION`; an
    unknown or foreign parent is rejected with `JOB_NOT_FOUND`.
    """
    if submit.parent_job_id is None:
        return
    parent = runtime._jobs.get(submit.parent_job_id)
    if parent is None or parent.submitter_principal != ctx.principal:
        raise JobNotFoundError(f"unknown parent_job_id: {submit.parent_job_id!r}")
    assert_lease_subset(
        submit.lease_request,
        parent.lease,
        parent_budget_remaining=parent.budget,
        parent_constraints=parent.lease_constraints,
        child_constraints=submit.lease_constraints,
    )


def _replay_idempotent(
    runtime: ARCPRuntime,
    ctx: SessionContext,
    env: Envelope,
    submit: JobSubmitPayload,
) -> bool:
    if submit.idempotency_key is None:
        return False
    entry = runtime.idempotency.get(ctx.principal, submit.idempotency_key)
    if entry is None:
        return False
    fp = runtime.idempotency.fingerprint(env.payload)
    if entry.submit_fingerprint != fp:
        raise DuplicateKeyError(
            f"idempotency key {submit.idempotency_key!r} already used with different parameters"
        )
    # Replay the accepted envelope so the duplicate caller receives a
    # `JobHandle`. Stamp a fresh request_id so the client's correlation
    # by request_id resolves the duplicate's submit future, not the original.
    accepted_wire = dict(entry.accepted_envelope)
    accepted_payload = dict(accepted_wire.get("payload", {}))
    accepted_payload["request_id"] = env.id
    accepted_wire["payload"] = accepted_payload
    ctx.stamp_and_enqueue(Envelope.from_wire(accepted_wire))
    # Prefer the entry's stored terminal envelope (set when the original
    # job finished). Fall back to the live Job's `last_terminal_envelope`
    # to cover the small window between terminal emission and the runner's
    # finally block running `set_terminal`.
    terminal_wire = entry.terminal_envelope
    if terminal_wire is None:
        job = runtime._jobs.get(entry.job_id)
        if job is not None and job.last_terminal_envelope is not None:
            terminal_wire = job.last_terminal_envelope
    if terminal_wire is not None:
        # Replay the terminal so the duplicate handle resolves promptly
        # instead of hanging on a terminal that has already happened.
        ctx.stamp_and_enqueue(Envelope.from_wire(terminal_wire))
    return True


async def _build_job_and_accept(  # noqa: PLR0913
    runtime: ARCPRuntime,
    ctx: SessionContext,
    env: Envelope,
    submit: JobSubmitPayload,
    name: str,
    version: str | None,
) -> tuple[Job, Envelope]:
    # PLR0913: private helper threading 4 distinct state sources that
    # would otherwise need a transient dataclass wrapper.
    job_id = new_job_id()
    budget = initial_budget_from_lease(submit.lease_request)
    job = Job(
        job_id=job_id,
        session=ctx,
        runtime=runtime,
        agent=name,
        agent_version=version,
        lease=submit.lease_request,
        lease_constraints=submit.lease_constraints,
        budget=dict(budget),
        initial_budget=dict(budget),
        parent_job_id=submit.parent_job_id,
        delegate_id=submit.delegate_id,
        trace_id=env.trace_id,
        submitter_principal=ctx.principal,
        idempotency_key=submit.idempotency_key,
    )
    runtime._jobs[job_id] = job
    credentials = await _issue_credentials(runtime, ctx, submit, job)
    job.credentials = credentials
    accepted = JobAcceptedPayload(
        job_id=job_id,
        agent=job.agent_ref,
        accepted_at=_now_iso(),
        lease=submit.lease_request,
        lease_constraints=submit.lease_constraints,
        budget=echo_budget_for_accept(budget),
        parent_job_id=submit.parent_job_id,
        delegate_id=submit.delegate_id,
        trace_id=env.trace_id,
        credentials=tuple(_credential_to_payload(c) for c in credentials) or None,
        request_id=env.id,
    )
    accept_env = Envelope(
        id=new_envelope_id(),
        type="job.accepted",
        session_id=ctx.session_id,
        job_id=job_id,
        trace_id=env.trace_id,
        payload=accepted.model_dump(mode="json", exclude_none=True),
    )
    return job, accept_env


async def _issue_credentials(
    runtime: ARCPRuntime,
    ctx: SessionContext,
    submit: JobSubmitPayload,
    job: Job,
) -> tuple[Credential, ...]:
    if runtime.credential_provisioner is None or not ctx.has_feature("provisioned_credentials"):
        return ()
    if runtime.revocation_log is None:
        raise InternalError("credential provisioner is configured but revocation_log is missing")
    provisioner_ctx = JobCredentialContext(
        job_id=job.job_id,
        agent=job.agent,
        agent_version=job.agent_version,
        submitter_principal=ctx.principal,
        parent_job_id=job.parent_job_id,
        lease=job.lease,
        lease_constraints=job.lease_constraints,
    )
    credentials: tuple[Credential, ...] = ()
    try:
        credentials = await runtime.credential_provisioner.issue(
            submit.lease_request, provisioner_ctx
        )
        for credential in credentials:
            _credential_to_payload(credential)
        for credential in credentials:
            await runtime.revocation_log.record(job.job_id, credential.id)
    except Exception as e:
        runtime._jobs.pop(job.job_id, None)
        for credential in credentials:
            with contextlib.suppress(Exception):
                await runtime.credential_provisioner.revoke(credential.id)
        raise InternalError(f"credential provisioner failed: {e}") from e
    return credentials


def _credential_to_payload(credential: Credential) -> CredentialPayload:
    constraints = None
    if credential.constraints is not None:
        constraints = CredentialConstraintsPayload.model_validate(
            {
                "cost.budget": credential.constraints.cost_budget,
                "model.use": credential.constraints.model_use,
                "expires_at": credential.constraints.expires_at,
            }
        )
    if credential.scheme != "bearer":
        raise ValueError("credential scheme must be 'bearer'")
    return CredentialPayload(
        id=credential.id,
        scheme="bearer",
        value=credential.value,
        endpoint=credential.endpoint,
        profile=credential.profile,
        constraints=constraints,
    )


async def handle_cancel(runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    _cancel = JobCancelPayload.model_validate(env.payload)
    if env.job_id is None:
        raise InvalidRequestError("job.cancel requires job_id on envelope")
    job = runtime._jobs.get(env.job_id)
    if job is None:
        raise JobNotFoundError(f"unknown job_id: {env.job_id}")
    if job.submitter_principal != ctx.principal:
        # Cancel from a non-submitter (e.g. a subscriber on another session)
        # is silently dropped per §7.6 / §14. Logging makes the audit trail
        # visible without tearing down the requester's session with a
        # session.error that would cascade and fail unrelated handles.
        runtime.logger.warning(
            "cancel_denied_non_submitter",
            session_id=ctx.session_id,
            principal=ctx.principal,
            job_id=env.job_id,
        )
        return
    # §7.4: acknowledge the cancel with `job.cancelled` before tearing the
    # task down. The subsequent terminal `job.error(CANCELLED)` is emitted by
    # the job runner's `_finalize_cancelled`.
    ack = Envelope(
        id=new_envelope_id(),
        type="job.cancelled",
        session_id=ctx.session_id,
        job_id=job.job_id,
        trace_id=job.trace_id,
        payload=JobCancelledPayload(job_id=job.job_id, request_id=env.id).model_dump(
            mode="json", exclude_none=True
        ),
    )
    ctx.stamp_and_enqueue(ack)
    task = runtime._job_tasks.get(env.job_id)
    if task is not None and not task.done():
        task.cancel()


async def handle_subscribe(runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    from .server import AuthorizationContext

    sub = JobSubscribePayload.model_validate(env.payload)
    job = runtime._jobs.get(sub.job_id)
    if job is None:
        raise JobNotFoundError(f"unknown job_id: {sub.job_id}")
    if not runtime.policy(
        AuthorizationContext(requester_principal=ctx.principal, job=job, operation="subscribe")
    ):
        raise PermissionDeniedError("not authorized to subscribe to this job")
    # Attach the subscriber to the job owner's *live* session: if the owner
    # resumed on a new connection, `job.session` is a stale pointer (#81).
    owner = runtime._sessions.get(job.session.session_id, job.session)
    owner.add_subscriber(job.job_id, ctx)
    replayed = await _replay_history(runtime, ctx, job, sub) if sub.history else 0
    subscribed = JobSubscribedPayload(
        request_id=env.id,
        job_id=job.job_id,
        current_status=job.state,
        agent=job.agent_ref,
        lease=job.lease,
        parent_job_id=job.parent_job_id,
        trace_id=job.trace_id,
        # The subscriber's own session-scoped seq watermark after any replay.
        subscribed_from=ctx.latest_event_seq,
        replayed=replayed,
    )
    out = Envelope(
        id=new_envelope_id(),
        type="job.subscribed",
        session_id=ctx.session_id,
        job_id=job.job_id,
        payload=subscribed.model_dump(mode="json", exclude_none=True),
    )
    ctx.stamp_and_enqueue(out)


async def _replay_history(
    runtime: ARCPRuntime,
    ctx: SessionContext,
    job: Job,
    sub: JobSubscribePayload,
) -> int:
    from_seq = sub.from_event_seq if sub.from_event_seq is not None else 0
    replayed = 0
    async for replayed_env_dict in runtime.event_log.read_since_seq(
        job.session.session_id, from_seq
    ):
        if replayed_env_dict.get("job_id") != job.job_id:
            continue
        # Clear event_seq so the subscriber session stamps its own (§8.3):
        # the merged stream stays strictly monotonic and gap-free.
        forward = Envelope.from_wire(replayed_env_dict).model_copy(
            update={
                "id": new_envelope_id(),
                "session_id": ctx.session_id,
                "event_seq": None,
            }
        )
        ctx.stamp_and_enqueue(forward)
        replayed += 1
    return replayed


async def handle_unsubscribe(runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    unsub = JobUnsubscribePayload.model_validate(env.payload)
    job = runtime._jobs.get(unsub.job_id)
    if job is None:
        return
    job.session.remove_subscriber(unsub.job_id, ctx.session_id)


__all__ = (
    "handle_ack",
    "handle_cancel",
    "handle_close",
    "handle_list_jobs",
    "handle_ping",
    "handle_submit",
    "handle_subscribe",
    "handle_unsubscribe",
)
