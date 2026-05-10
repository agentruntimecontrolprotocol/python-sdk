"""Default client-side handlers for runtime-driven prompts.

The runtime emits envelopes that ask the *client* to do something, e.g.
``human.input.request`` or ``permission.request``. A real client wires these
into its UI; for tests and examples we provide stub handlers that resolve
them via simple callables.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from arcp.client.client import ARCPClient
from arcp.envelope import Envelope

HumanInputResolver = Callable[[Envelope], Awaitable[Any]]
HumanChoiceResolver = Callable[[Envelope], Awaitable[str]]
PermissionDecider = Callable[[Envelope], Awaitable[tuple[bool, str | None]]]


@dataclass
class ClientHandlers:
    """Bind resolver callables for runtime-driven prompts.

    Construct with whichever resolvers you have. The :meth:`pump` coroutine
    runs in the background and dispatches every event from
    :meth:`ARCPClient.events` to the matching resolver.
    """

    client: ARCPClient
    human_input: HumanInputResolver | None = None
    human_choice: HumanChoiceResolver | None = None
    permission: PermissionDecider | None = None

    async def pump(self) -> None:
        """Continuously consume events and route runtime prompts to resolvers."""

        async for env in self.client.events():
            await self._dispatch(env)

    async def _dispatch(self, env: Envelope) -> None:
        if env.type == "human.input.request" and self.human_input is not None:
            value = await self.human_input(env)
            await self.client.send(
                Envelope(
                    id=f"resp_{env.id}",
                    type="human.input.response",
                    session_id=env.session_id,
                    correlation_id=env.id,
                    payload={"value": value},
                )
            )
        elif env.type == "human.choice.request" and self.human_choice is not None:
            choice_id = await self.human_choice(env)
            await self.client.send(
                Envelope(
                    id=f"resp_{env.id}",
                    type="human.choice.response",
                    session_id=env.session_id,
                    correlation_id=env.id,
                    payload={"choice_id": choice_id},
                )
            )
        elif env.type == "permission.request" and self.permission is not None:
            granted, reason = await self.permission(env)
            if granted:
                await self.client.send(
                    Envelope(
                        id=f"grant_{env.id}",
                        type="permission.grant",
                        session_id=env.session_id,
                        correlation_id=env.id,
                        payload={
                            "permission": env.payload["permission"],
                            "lease_seconds": env.payload.get(
                                "requested_lease_seconds", 300
                            ),
                        },
                    )
                )
            else:
                await self.client.send(
                    Envelope(
                        id=f"deny_{env.id}",
                        type="permission.deny",
                        session_id=env.session_id,
                        correlation_id=env.id,
                        payload={
                            "permission": env.payload["permission"],
                            "reason": reason or "denied",
                        },
                    )
                )


__all__ = [
    "ClientHandlers",
    "HumanChoiceResolver",
    "HumanInputResolver",
    "PermissionDecider",
]
