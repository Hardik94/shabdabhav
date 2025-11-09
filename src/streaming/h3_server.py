import argparse
import asyncio
import base64
import json
import os
import signal
import tempfile
from pathlib import Path
from typing import Dict, Optional

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.h3.connection import H3_ALPN, H3Connection
from aioquic.h3.events import DataReceived, HeadersReceived
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted, ConnectionTerminated

from src.streaming.engines.tts_cli import synthesize_with_piper
from src.streaming.engines.parler_cli import synthesize_with_parler
from src.common.config import models_root
from src.streaming.engines.hf_whisper import transcribe_with_hf_whisper
from src.streaming.engines.stt_cli import transcribe_with_whisper_cpp
from src.common.config import models_root


def _hdrs(status: int, content_type: bytes = b"application/json"):
    return [
        (b":status", str(status).encode()),
        (b"server", b"shabdabhav-quic/1.0"),
        (b"content-type", content_type),
    ]


class EngineProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._http: Optional[H3Connection] = None
        self._buf: Dict[int, bytearray] = {}
        self._meta: Dict[int, Dict] = {}

    def quic_event_received(self, event):
        if isinstance(event, HandshakeCompleted):
            try:
                peer = f"{self._quic._network_paths[0].addr[0]}:{self._quic._network_paths[0].addr[1]}"
            except Exception:
                peer = "?"
            print(f"[engine] QUIC handshake from {peer}")
        if isinstance(event, ConnectionTerminated):
            reason = getattr(event, "reason_phrase", "")
            if isinstance(reason, (bytes, bytearray)):
                try:
                    reason = reason.decode(errors="ignore")
                except Exception:
                    reason = str(reason)
            print(f"[engine] QUIC terminated: {event.error_code} {reason}")
        if self._http is None:
            self._http = H3Connection(self._quic)
        for http_event in self._http.handle_event(event):
            if isinstance(http_event, HeadersReceived):
                headers = {k.decode().lower(): v.decode() for k, v in http_event.headers}
                method = headers.get(":method", "GET").upper()
                path = headers.get(":path", "/")
                self._meta[http_event.stream_id] = {"method": method, "path": path, "headers": headers}
                self._buf[http_event.stream_id] = bytearray()
            elif isinstance(http_event, DataReceived):
                self._buf[http_event.stream_id].extend(http_event.data)
                if http_event.stream_ended:
                    asyncio.create_task(self._route(http_event.stream_id))

    def _send_json(self, sid: int, status: int, obj: Dict):
        assert self._http is not None
        self._http.send_headers(sid, _hdrs(status))
        self._http.send_data(sid, json.dumps(obj).encode(), end_stream=True)

    def _send_blob(self, sid: int, status: int, blob: bytes, content_type: bytes):
        assert self._http is not None
        self._http.send_headers(sid, _hdrs(status, content_type))
        self._http.send_data(sid, blob, end_stream=True)

    async def _route(self, sid: int):
        meta = self._meta.pop(sid, {})
        body = bytes(self._buf.pop(sid, b""))
        method = meta.get("method", "GET")
        path = meta.get("path", "/")
        try:
            if method == "GET" and path == "/health":
                self._send_json(sid, 200, {"status": "ok"})
                return

            if method == "POST" and path == "/v1/stream/audio/speech":
                req = json.loads(body or b"{}")
                text = str(req.get("text", "")).strip()
                model = str(req.get("model", "")).strip()
                voice = req.get("voice")
                description = req.get("description")
                if not text or not model:
                    self._send_json(sid, 400, {"error": "text and model required"})
                    return
                try:
                    # Guard: prevent STT models from being used on TTS endpoint
                    def _looks_like_whisper(m: str) -> bool:
                        if m.startswith("ggml-"):
                            return True
                        if m.endswith(".gguf") or m.endswith(".bin"):
                            return True
                        # Check local dir with gguf/bin inside
                        ld = models_root() / m
                        if ld.exists() and ld.is_dir():
                            for f in ld.glob("*.gguf"):
                                return True
                            for f in ld.glob("*.bin"):
                                return True
                        return False

                    if _looks_like_whisper(model):
                        self._send_json(sid, 400, {"error": "Whisper/STT models are not valid for TTS. Use /v1/stream/audio/transcriptions."})
                        return

                    # Determine if this should use Parler runtime
                    def _looks_like_parler(m: str) -> bool:
                        if m.startswith("parler-tts"):
                            return True
                        # Check if there is a local model directory with Parler artifacts
                        local_dir = models_root() / m
                        if local_dir.exists() and local_dir.is_dir():
                            if (local_dir / "config.json").exists():
                                return True
                            if (local_dir / "pytorch_model.bin").exists():
                                return True
                            # safetensors variant
                            for f in local_dir.glob("*.safetensors"):
                                return True
                        return False

                    if _looks_like_parler(model):
                        # Optional Parler runtime (requires extra deps)
                        try:
                            blob = await synthesize_with_parler(text=text, model=model, description=description)
                        except FileNotFoundError as e:
                            self._send_json(sid, 501, {"error": str(e)})
                            return
                    else:
                        # Piper via subprocess
                        blob = await synthesize_with_piper(text=text, model=model, voice=voice)
                except FileNotFoundError as e:
                    self._send_json(sid, 404, {"error": str(e)})
                    return
                except Exception as e:
                    self._send_json(sid, 500, {"error": f"tts error: {e}"})
                    return
                self._send_blob(sid, 200, blob, b"audio/wav")
                return

            if method == "POST" and path == "/v1/stream/audio/transcriptions":
                req = json.loads(body or b"{}")
                model = str(req.get("model", "")).strip() or "whisper-1"
                language = req.get("language")
                audio_b64 = req.get("audio_b64")
                if not audio_b64:
                    self._send_json(sid, 400, {"error": "audio_b64 required"})
                    return
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                except Exception:
                    self._send_json(sid, 400, {"error": "invalid base64"})
                    return
                try:
                    def _looks_like_hf_whisper(m: str) -> bool:
                        if m.startswith("openai/whisper-"):
                            return True
                        # Known aliases
                        if m in {"whisper-tiny", "whisper-base", "whisper-small", "whisper-medium", "whisper-large", "whisper-large-v2"}:
                            return True
                        return False

                    if _looks_like_hf_whisper(model):
                        result = await transcribe_with_hf_whisper(audio_bytes, model_id=(model if model.startswith("openai/") else f"openai/{model}"), language=language)
                    else:
                        result = await transcribe_with_whisper_cpp(audio_bytes, model=model, language=language)
                except FileNotFoundError as e:
                    self._send_json(sid, 404, {"error": str(e)})
                    return
                except Exception as e:
                    self._send_json(sid, 500, {"error": f"stt error: {e}"})
                    return
                self._send_blob(sid, 200, json.dumps(result).encode(), b"application/json")
                return

            self._send_json(sid, 404, {"error": "not found"})
        except Exception as exc:
            self._send_json(sid, 500, {"error": str(exc)})


async def main_async(host: str, port: int, cert: Path, key: Path):
    cfg = QuicConfiguration(is_client=False, alpn_protocols=H3_ALPN)
    cfg.load_cert_chain(certfile=str(cert), keyfile=str(key))
    server = await serve(host, port, configuration=cfg, create_protocol=lambda *a, **kw: EngineProtocol(*a, **kw))
    print(f"[engine] listening on https://{host}:{port} (HTTP/3)")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    try:
        await stop.wait()
    finally:
        try:
            server.close()
        except Exception:
            pass


def run():
    parser = argparse.ArgumentParser(description="Shabdabhav QUIC Streaming Engine")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9443)
    parser.add_argument("--cert", type=Path, default=Path("./quic_cert.pem"))
    parser.add_argument("--key", type=Path, default=Path("./quic_key.pem"))
    args = parser.parse_args()
    asyncio.run(main_async(args.host, args.port, args.cert, args.key))


if __name__ == "__main__":
    run()


