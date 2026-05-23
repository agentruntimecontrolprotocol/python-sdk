"""stream-resume — long-form writer that pipes GLM-5 streaming deltas through chunked result.

A long-form writer agent streams a generated article through ARCP's
chunked-result primitive. The runtime persists every emitted envelope
in its EventLog under the session's monotonic event_seq, which lets a
client reconnect after a transport drop and replay the chunks it
missed (see the companion client.py for the resume side).

Highlights: §8.4 ctx.stream_result() with `write()` per delta batch
and a `close()` that emits the terminating job.result with a
result_id; §13.3 / §6.3 the EventLog + resume_window_sec wiring that
makes the session resumable; GLM-5 streaming via the OpenAI-compatible
z.ai endpoint pipes naturally into the chunked stream.
"""

from __future__ import annotations

import asyncio
import os

import openai

from arcp import RuntimeInfo, serve_websocket
from arcp.runtime import ARCPRuntime, InMemoryEventLog, JobContext, StaticBearerVerifier

PORT = int(os.environ.get("ARCP_DEMO_PORT", "7901"))
TOKEN = os.environ.get("ARCP_DEMO_TOKEN", "demo-token")

# GLM-5 via z.ai's OpenAI-compatible API. Swap base_url for BigModel or
# another GLM provider; the OpenAI SDK shape stays the same.
GLM_BASE_URL = os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4/")


async def long_form(input: dict, ctx: JobContext) -> None:
    glm = openai.AsyncOpenAI(api_key=os.environ.get("ZAI_API_KEY"), base_url=GLM_BASE_URL)
    completion = await glm.chat.completions.create(
        model="glm-5",
        stream=True,
        messages=[{"role": "user", "content": f"Write a 2000-word article on: {input['topic']}"}],
    )

    buf = ""
    async with ctx.stream_result() as stream:
        async for chunk in completion:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if not delta:
                continue
            buf += delta
            # flush in paragraph-sized batches — one result_chunk envelope per
            # ~200 chars keeps the seq stream readable without flooding the
            # EventLog with single-token events
            if len(buf) >= 200:
                await stream.write(buf)
                buf = ""
        if buf:
            await stream.write(buf)
        # close emits the terminal job.result carrying result_id and
        # result_size; inline `result` MUST NOT be used in chunked mode
        await stream.close(summary=f"Article on {input['topic']}")


async def main() -> None:
    # resume needs a persistent EventLog and a resume window. without these
    # the runtime would treat a dropped transport as a closed session.
    runtime = ARCPRuntime(
        runtime=RuntimeInfo(name="writer", version="1.0.0"),
        bearer=StaticBearerVerifier({TOKEN: "demo-principal"}),
        event_log=InMemoryEventLog(),
        resume_window_sec=60,
    )
    runtime.register_agent("long-form", long_form)
    server = await serve_websocket(runtime.accept, host="127.0.0.1", port=PORT, path="/arcp")
    print(f"listening on ws://127.0.0.1:{PORT}/arcp")
    try:
        await asyncio.Future()
    finally:
        server.close()
        await server.wait_closed()
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
