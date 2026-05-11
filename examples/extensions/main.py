"""SDR domain via custom `arcpx.sdr.*.v1` extension messages.

Tune to 145.500 MHz (2 m FM calling), capture 5 s of IQ at 2.048 MS/s,
NBFM-demodulate to 48 kHz PCM. Exercises §21 naming, capability
advertisement, and unknown-message handling.
"""

from __future__ import annotations

import asyncio
import uuid

from arcp import ARCPClient, ARCPError, ErrorCode

EXT_TUNE = "arcpx.sdr.tune.v1"
EXT_GAIN = "arcpx.sdr.gain.v1"
EXT_CAPTURE = "arcpx.sdr.capture.v1"
EXT_DEMODULATE = "arcpx.sdr.demodulate.v1"
ALL_EXTENSIONS = (EXT_TUNE, EXT_GAIN, EXT_CAPTURE, EXT_DEMODULATE)


async def main() -> None:
    # capabilities.extensions=list(ALL_EXTENSIONS) on the open call.
    client = ARCPClient(...)
    accepted = await client.open()

    # If the runtime didn't advertise our required extension set,
    # refuse the session — RFC §7 / §21.2.
    advertised = set(accepted.capabilities.extensions or ())
    if not set(ALL_EXTENSIONS).issubset(advertised):
        raise ARCPError(
            ErrorCode.UNIMPLEMENTED,
            f"runtime missing SDR extensions: {advertised}",
        )

    handle = uuid.uuid4().hex[:8]

    await client.request(
        client.envelope(
            EXT_TUNE,
            payload={
                "center_freq_hz": 145_500_000.0,
                "sample_rate_hz": 2_048_000.0,
                "ppm_correction": 1,
            },
        ),
        timeout=10.0,
    )
    await client.request(
        client.envelope(
            EXT_GAIN,
            payload={"stages": [{"name": "TUNER", "value_db": 28.0}]},
        ),
        timeout=10.0,
    )

    # Capture returns an artifact.ref pointing at the IQ buffer.
    # The buffer never travels inline — demodulate references it.
    cap = await client.request(
        client.envelope(
            EXT_CAPTURE,
            payload={
                "seconds": 5.0,
                "capture_handle": handle,
                "decimate": 1,
            },
        ),
        timeout=15.0,
    )
    iq_artifact = str(cap.payload["artifact_id"])
    print(f"captured IQ → {iq_artifact}")

    audio = await client.request(
        client.envelope(
            EXT_DEMODULATE,
            payload={
                "iq_artifact_id": iq_artifact,
                "mode": "NBFM",
                "audio_rate_hz": 48_000,
            },
        ),
        timeout=15.0,
    )
    print(f"demod  PCM → {audio.payload.get('artifact_id')}")

    # §21.3 demonstration: unadvertised extension marked optional.
    # Runtime SHOULD ack (silent drop) rather than nack.
    optional = await client.request(
        client.envelope(
            "arcpx.sdr.experimental_doppler.v1",
            extensions={"optional": True},
            payload={"velocity_mps": 7.4},
        ),
        timeout=5.0,
    )
    print(f"optional unknown → {optional.type}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
