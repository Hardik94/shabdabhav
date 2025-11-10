# Shabdabhav Streaming API (Two-Container Architecture)

This directory contains two services:

- Gateway (FastAPI, HTTP/1.1 + JSON): OpenAI-compatible endpoints, auth, rate limiting, model downloader.
- Streaming Engine (HTTP/3 over QUIC): Low-latency TTS/STT using local binaries (no heavy Python ML deps).

## Directory layout

- Models directory: `data/models` (mounted to host)
- Audio data directory: `data/audio` (mounted to host)

Both directories are created on first run.

## Environment variables

- `API_TOKENS`: optional comma-separated tokens for gateway auth
- `STREAM_ENGINE_BASE`: gateway → engine base URL, e.g. `https://localhost:9443`
- `QUIC_INSECURE`: set to `1` to skip TLS verification in dev
- `PIPER_BIN`: absolute path to Piper binary inside container/host
- `WHISPER_CPP_BIN`: absolute path to whisper.cpp binary inside container/host

## Available Models 

Details version can be found at [models.md](models.md)


| Model | TTS | STT |
|--|--|--|
| parler-tts | ✅	|   |
| piper | ✅ |   |
| whisper-cpp |  | ✅ |  


## Run locally (without Docker)

1) Start QUIC engine (HTTP/3):

```bash
shabda-quic --host 0.0.0.0 --port 9443 --cert ./quic_cert.pem --key ./quic_key.pem
```

2) Start Gateway (HTTP/1.1):

```bash
export STREAM_ENGINE_BASE=https://localhost:9443
export QUIC_INSECURE=1
shabda-gateway
```

## Model management (no huggingface required)

Download a model file (GGUF/BIN/ONNX) directly by URL into `data/models/<name>`:

```bash
curl -X POST http://localhost:8000/v1/models/download \
  -H 'Content-Type: application/json' \
  -d '{
    "name":"whisper-large-v3",
    "url":"https://example.com/models/ggml-large-v3.gguf",
    "format":"gguf"
  }'
```

List models:

```bash
curl http://localhost:8000/v1/models
```

## TTS (Gateway → QUIC → Piper)

Requirements:
- Place a Piper `.onnx` model and its matching `.onnx.json` under `data/models/<piper-voice>/`.
- Provide `PIPER_BIN` pointing to Piper binary.

Request:

```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello world","model":"piper-voice-dir-name"}' \
  --output out.wav
```

Generated audio is also saved under `data/audio/tts/`.

## STT (Gateway → QUIC → whisper.cpp)

Requirements:
- Place a whisper `.gguf` or `.bin` model under `data/models/<whisper-model>/`.
- Provide `WHISPER_CPP_BIN` pointing to whisper.cpp main binary.

Request:

```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -F "file=@/path/to/audio.wav" \
  -F "model=whisper-large-v3" \
  -F "response_format=json"
```

Uploaded audio and transcripts are saved under `data/audio/stt/`.

## Docker Compose

A `docker-compose.yml` is provided at the repo root to run both services. It mounts `./data/models` and `./data/audio` from the host to ensure persistence and sharing between containers.

```bash
# Start both services
docker compose up -d --build

# View logs
docker compose logs -f gateway
```

Notes:
- Provide Linux-compatible binaries for Piper and whisper.cpp inside the containers (via volumes) or bake them into images.
- For local development, QUIC TLS verification is disabled by setting `QUIC_INSECURE=1` on the gateway.

### Environment variables (.env)

You can set environment variables via `.env` at repo root (compose loads it for both services):

```
# Gateway auth tokens (comma-separated). Leave empty to disable auth.
API_TOKENS=

# Gateway -> QUIC base URL and TLS behavior
STREAM_ENGINE_BASE=https://quic:9443
QUIC_INSECURE=1

# Hugging Face access token (optional) for authenticated/rate-limited downloads
HUGGINGFACE_TOKEN=

# QUIC engine binaries (must exist inside container)
PIPER_BIN=/usr/local/bin/piper
WHISPER_CPP_BIN=/usr/local/bin/whisper-cpp
```

Compose will also accept overrides in the `environment:` block.


