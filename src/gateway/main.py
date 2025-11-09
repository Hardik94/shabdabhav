import asyncio
import json
import socket
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse, PlainTextResponse

from src.common.auth import require_auth
from src.common.rate_limiter import SlidingWindowRateLimiter, client_key
from src.common.model_store import (
    list_models,
    download_model,
    download_whisper,
    download_parler_tts,
    download_piper_voice,
)
from src.common.config import quic_base_url, quic_cert_paths, insecure_quic


app = FastAPI(title="Shabdabhav Gateway", version="1.0.0")

rate_limiter = SlidingWindowRateLimiter(max_requests=120, window_seconds=60)


@app.middleware("http")
async def _auth_and_rate(request: Request, call_next):
    await require_auth(request)
    try:
        rate_limiter.check(client_key(request))
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    return await call_next(request)


@app.get("/")
async def root():
    return {
        "name": "shabdabhav-gateway",
        "time": time.time(),
        "quic_base": quic_base_url(),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def models_list():
    return {"data": list_models()}


@app.post("/v1/models/download")
async def models_download(request: Request):
    body = await request.json()
    name = str(body.get("name", "")).strip()
    url = (body.get("url") or "").strip()
    fmt = body.get("format")
    voice = body.get("voice")
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    try:
        # Parler-TTS: model name like "parler-tts/parler-tts-mini-v1"
        if name.startswith("parler-tts/"):
            return download_parler_tts(name)

        # Piper voices (ONNX dataset) go to data dir
        if name == "piper-tts":
            if not voice:
                raise HTTPException(status_code=400, detail="voice required for piper-tts")
            return download_piper_voice(voice)

        # Whisper GGUF/BIN by canonical names
        if name.endswith(".bin") or name.endswith(".gguf") or name.startswith("ggml-"):
            return download_whisper(name, url=url or None)

        # Fallback: direct URL to models dir
        if not url:
            raise HTTPException(status_code=400, detail="url required for generic download")
        return download_model(name=name, url=url, format_hint=fmt)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------- OpenAI compatibility (basic) ----------


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Compatibility stub - no local LLM; echo system
    body = await request.json()
    messages = body.get("messages", [])
    last = messages[-1]["content"] if messages else ""
    return {
        "id": f"chatcmpl-{int(time.time()*1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "stub-echo"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": f"echo: {last}"},
                "finish_reason": "stop",
            }
        ],
    }


async def _http3_post_json_bytes(path: str, payload: dict) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    # Lightweight HTTP/3 client adapted from demo, for protocol translation
    from aioquic.asyncio import connect
    from aioquic.h3.connection import H3_ALPN, H3Connection
    from aioquic.h3.events import HeadersReceived, DataReceived
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.asyncio import QuicConnectionProtocol

    base = quic_base_url()
    if not base:
        raise HTTPException(status_code=502, detail="STREAM_ENGINE_BASE not configured")
    assert base.startswith("https://")
    host_port = base[len("https://") :]
    if "/" in host_port:
        host_port = host_port.split("/")[0]
    host, port_s = host_port.split(":") if ":" in host_port else (host_port, "443")
    port = int(port_s)

    cfg = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
    if insecure_quic():
        import ssl as _ssl
        cfg.verify_mode = _ssl.CERT_NONE
    cert, key = quic_cert_paths()
    if cert and key:
        cfg.load_cert_chain(str(cert), str(key))

    class _Client(QuicConnectionProtocol):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.http: Optional[H3Connection] = None
            self.headers: list[tuple[bytes, bytes]] = []
            self.body = bytearray()
            self.done = asyncio.Event()
            self.status = 0

        def quic_event_received(self, event):
            if self.http is None:
                self.http = H3Connection(self._quic)
            for ev in self.http.handle_event(event):
                if isinstance(ev, HeadersReceived):
                    self.headers = ev.headers
                    for k, v in self.headers:
                        if k == b":status":
                            try:
                                self.status = int(v.decode())
                            except Exception:
                                self.status = 0
                elif isinstance(ev, DataReceived):
                    if ev.data:
                        self.body.extend(ev.data)
                    if ev.stream_ended:
                        self.done.set()

        def send(self, authority: str, _path: str, data: bytes):
            if self.http is None:
                self.http = H3Connection(self._quic)
            stream_id = self._quic.get_next_available_stream_id()
            headers = [
                (b":method", b"POST"),
                (b":scheme", b"https"),
                (b":authority", authority.encode()),
                (b":path", _path.encode()),
                (b"content-type", b"application/json"),
            ]
            self.http.send_headers(stream_id, headers)
            self.http.send_data(stream_id, data, end_stream=True)
            self.transmit()

    async with connect(host, port, configuration=cfg, create_protocol=_Client) as proto:  # type: ignore[arg-type]
        body = json.dumps(payload).encode()
        authority = f"{host}:{port}"
        proto.send(authority, path, body)  # type: ignore[attr-defined]
        await asyncio.wait_for(proto.done.wait(), timeout=60)  # type: ignore[attr-defined]
        return proto.status, proto.headers, bytes(proto.body)  # type: ignore[attr-defined]


@app.post("/v1/audio/speech")
async def audio_speech(request: Request):
    body = await request.json()
    # If QUIC backend configured, translate protocol
    base = quic_base_url()
    if base:
        status, headers, blob = await _http3_post_json_bytes("/v1/stream/audio/speech", body)
        if status != 200:
            try:
                detail = json.loads(blob.decode()).get("error", f"backend status {status}")
            except Exception:
                detail = f"backend status {status}"
            raise HTTPException(status_code=502, detail=detail)
        return StreamingResponse(iter([blob]), media_type="audio/wav")
    # Fallback: instruct client to use streaming endpoint directly if configured
    raise HTTPException(status_code=501, detail="Streaming engine not configured")


@app.post("/v1/audio/transcriptions")
async def audio_transcriptions(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    response_format: str = Form("json"),
):
    base = quic_base_url()
    if not base:
        raise HTTPException(status_code=501, detail="Streaming engine not configured")

    # Transport the small payload as base64 JSON to QUIC for simplicity
    import base64, tempfile, os as _os
    with tempfile.NamedTemporaryFile(delete=False, suffix="-upload") as tmp:
        uploaded_path = tmp.name
        tmp.write(await file.read())
    try:
        with open(uploaded_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        payload = {"model": model, "language": language, "audio_b64": b64}
        status, headers, blob = await _http3_post_json_bytes("/v1/stream/audio/transcriptions", payload)
        if status != 200:
            try:
                detail = json.loads(blob.decode()).get("error", f"backend status {status}")
            except Exception:
                detail = f"backend status {status}"
            raise HTTPException(status_code=502, detail=detail)
        result = json.loads(blob.decode() or "{}")
    finally:
        try:
            _os.unlink(uploaded_path)
        except Exception:
            pass

    text_out = (result.get("text") or "").strip()
    if response_format in (None, "", "json"):
        return {"text": text_out}
    if response_format == "text":
        return PlainTextResponse(text_out)
    if response_format == "verbose_json":
        return result
    raise HTTPException(status_code=400, detail=f"Unsupported response_format: {response_format}")


@app.post("/v1/images/generations")
async def images_generations():
    raise HTTPException(status_code=501, detail="Image generation not implemented")


def run():
    import uvicorn
    uvicorn.run("src.gateway.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    run()


