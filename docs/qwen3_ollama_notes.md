# Ollama and `qwen3:4b` notes

`pythalab-agent-cli` is tuned around a single small model: [`qwen3:4b`](https://ollama.com/library/qwen3) served via Ollama. This page collects the practical bits.

## Pulling the model

```bash
ollama pull qwen3:4b
```

`models.fallback_model` defaults to the same image, so a single pull covers both slots. To use a different fallback (e.g. for graceful degradation when the GPU is busy), edit `configs/models.yaml`:

```yaml
default_model: qwen3:4b
fallback_model: qwen3:4b
base_url: http://localhost:11434
```

## Running the daemon

The recommended environment for a 6 GB GPU:

```bash
OLLAMA_NUM_PARALLEL=1 \
OLLAMA_MAX_LOADED_MODELS=1 \
OLLAMA_MAX_QUEUE=16 \
OLLAMA_FLASH_ATTENTION=1 \
OLLAMA_KV_CACHE_TYPE=q8_0 \
ollama serve
```

| Variable                    | Why                                                                                  |
| --------------------------- | ------------------------------------------------------------------------------------ |
| `OLLAMA_NUM_PARALLEL=1`     | One generation at a time. Avoids OOM with longer contexts.                            |
| `OLLAMA_MAX_LOADED_MODELS=1`| Only one model resident in VRAM at a time.                                            |
| `OLLAMA_MAX_QUEUE=16`       | Bounded queue.                                                                        |
| `OLLAMA_FLASH_ATTENTION=1`  | Lower memory cost on supported GPUs.                                                  |
| `OLLAMA_KV_CACHE_TYPE=q8_0` | Quantised KV cache; halves cache memory at negligible quality loss for short tasks.   |

If you do not start Ollama yourself, `pythalab-agent run` starts it via [llm/ollama_service.py](../src/pythalab_agent_cli/llm/ollama_service.py) with the same environment, and stops it again after the run.

## The "direct" profile

The agent uses one model role, `direct`, defined in `configs/models.yaml`:

```yaml
profiles:
  direct:
    think: true
    temperature: 0.4
    top_p: 0.9
    num_ctx: 16384
    num_predict: -1
    keep_alive: 30m
```

| Key            | Effect                                                                                                |
| -------------- | ----------------------------------------------------------------------------------------------------- |
| `think: true`  | Tells `qwen3` to emit `<think>…</think>` blocks. The runtime streams these to the observer live.       |
| `temperature`  | Lower for code; 0.4 is a good sweet spot for `qwen3:4b`.                                              |
| `top_p`        | Nucleus sampling; 0.9 is the usual default.                                                           |
| `num_ctx`      | Context length. 16384 fits a typical task + prior attempt + validator report on 6 GB VRAM.            |
| `num_predict`  | `-1` means "until EOS". Bound it (e.g. 4096) if you want predictable upper-bound latency per attempt. |
| `keep_alive`   | How long the model stays loaded after a request. Long values keep the second `run` call snappy.       |

If you hit out-of-memory: drop `num_ctx` to 8192 or 4096 first, then disable `think`.

## How the client talks to Ollama

[llm/ollama_client.py](../src/pythalab_agent_cli/llm/ollama_client.py):

- POSTs `/api/chat` with `messages`, `options` (the profile), and `stream` set to `True` when `think` is on or a `stream_callback` is provided.
- In streaming mode the response is NDJSON; the client concatenates `message.content` and forwards `message.thinking` chunks (and `<think>…</think>`-tagged content) to the observer.
- In non-streaming mode it returns the full response in one shot.
- Timeout from `direct.request_timeout_sec` (default 600 s).

## Trying another model

You can point `default_model` at any `qwen3:*` or compatible chat model in your local Ollama. There are no `qwen3`-only assumptions in the runtime apart from:

- The system prompt assumes the model can follow "respond with a single fenced ```` ```python ```` block".
- The `think: true` flag is a no-op on models that do not support it; the loop still works, you just lose the thinking stream.

If a model does not understand fenced code blocks, the extractor will fail and the loop will keep nudging the model with reminders until it complies or the budget runs out.
