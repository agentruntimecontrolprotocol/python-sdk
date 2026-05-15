# submit_and_stream

Demonstrates spec §13.1 / §7.1 / §8.2: an agent emits 7 of the 8 reserved
event kinds (`status`, `log`, `thought`, `tool_call`, `tool_result`,
`metric`, `artifact_ref`) and the client awaits the terminal `job.result`.

## Run

```sh
python examples/submit_and_stream/server.py    # terminal 1
python examples/submit_and_stream/client.py    # terminal 2
```

Client exits 0 when `result.final_status == "success"` and at least 7
events were observed.
