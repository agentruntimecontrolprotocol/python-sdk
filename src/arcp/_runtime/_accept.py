"""Server-side session accept-loop and read pump."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from .._envelope import Envelope
from .._errors import ARCPError, InternalError, InvalidRequestError, UnauthenticatedError
from .._messages.session import SessionErrorPayload
from .._transport.base import Transport, TransportClosed
from .._ulid import new_envelope_id
from .session import heartbeat_loop, write_pump

if TYPE_CHECKING:
    from .server import ARCPRuntime
    from .session import SessionContext


async def run_session(runtime: ARCPRuntime, transport: Transport) -> None:
    """Handshake then drive read pump + heartbeat under a TaskGroup."""
    ctx = await _accept_or_close(runtime, transport)
    if ctx is None:
        return
    send_queue = ctx._send_queue
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(write_pump(transport, send_queue))
            _maybe_start_heartbeat(ctx)
            tg.create_task(_read_pump(runtime, ctx))
    except* TransportClosed:
        pass
    except* asyncio.CancelledError:
        pass
    finally:
        send_queue.put_nowait(None)
        runtime._sessions.pop(ctx.session_id, None)


async def _accept_or_close(runtime: ARCPRuntime, transport: Transport) -> SessionContext | None:
    from ._handshake import perform_handshake

    try:
        return await perform_handshake(runtime, transport)
    except UnauthenticatedError as e:
        await _send_close_error(transport, e)
    except InvalidRequestError as e:
        await _send_close_error(transport, e)
    except Exception as e:
        await _send_close_error(transport, InternalError(str(e)))
    await transport.close()
    return None


def _maybe_start_heartbeat(ctx: SessionContext) -> asyncio.Task[Any] | None:
    if not (ctx.has_feature("heartbeat") and ctx.state.heartbeat_interval_sec):
        return None
    ctx.heartbeat_outcome = asyncio.get_event_loop().create_future()
    return asyncio.create_task(
        heartbeat_loop(ctx, interval=float(ctx.state.heartbeat_interval_sec))
    )


async def _send_close_error(transport: Transport, err: ARCPError) -> None:
    env = Envelope(
        id=new_envelope_id(),
        type="session.error",
        payload=SessionErrorPayload(
            code=err.code, message=err.message, retryable=err.retryable
        ).model_dump(mode="json"),
    )
    try:
        await transport.send(env.to_wire())
    except TransportClosed:
        return


async def _read_pump(runtime: ARCPRuntime, ctx: SessionContext) -> None:
    try:
        while True:
            raw = await ctx.transport.recv()
            ctx.record_inbound()
            try:
                env = Envelope.from_wire(raw)
            except Exception as e:
                await _emit_session_error(ctx, InvalidRequestError(str(e)))
                continue
            await _dispatch_one(runtime, ctx, env)
    except TransportClosed:
        raise


async def _dispatch_one(runtime: ARCPRuntime, ctx: SessionContext, env: Envelope) -> None:
    try:
        await runtime._dispatch(ctx, env)
    except ARCPError as e:
        await _emit_session_error(ctx, e)
    except Exception as e:
        runtime.logger.exception("dispatch_failed", error=str(e))
        await _emit_session_error(ctx, InternalError(str(e)))


async def _emit_session_error(ctx: SessionContext, err: ARCPError) -> None:
    env = Envelope(
        id=new_envelope_id(),
        type="session.error",
        session_id=ctx.session_id,
        payload=SessionErrorPayload(
            code=err.code, message=err.message, retryable=err.retryable
        ).model_dump(mode="json"),
    )
    ctx.stamp_and_enqueue(env)


__all__ = ("run_session",)
