import json
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Optional

from .config import models_root, data_root


def ensure_model_dir(name: str) -> Path:
    base = models_root() / name
    base.mkdir(parents=True, exist_ok=True)
    return base


def list_models() -> list[dict]:
    out: list[dict] = []
    for child in models_root().glob("*"):
        if child.is_dir():
            files = [p.name for p in child.iterdir() if p.is_file()]
            out.append({"id": child.name, "files": files})
    return out


def _filename_from_url(url: str) -> str:
    base = url.split("?")[0].rstrip("/")
    return base.split("/")[-1]


def download_file(url: str, dest_path: Path, resume: bool = True) -> Path:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    headers: dict[str, str] = {
        "User-Agent": "shabdabhav/1.0",
        "Accept": "application/octet-stream, */*",
    }
    # Optional: Hugging Face token for authenticated downloads
    hf_token = os.getenv("HUGGINGFACE_TOKEN")
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"
    mode = "wb"
    if resume and tmp_path.exists():
        existing = tmp_path.stat().st_size
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(tmp_path, mode) as f:
        shutil.copyfileobj(resp, f, length=1024 * 1024)

    tmp_path.replace(dest_path)
    return dest_path


def download_model(name: str, url: str, format_hint: Optional[str] = None) -> dict:
    base = ensure_model_dir(name)
    filename = _filename_from_url(url)
    if format_hint and not filename.endswith(f".{format_hint}"):
        # keep remote filename but record hint
        pass
    target = base / filename
    path = download_file(url, target, resume=True)
    meta = {"name": name, "file": path.name, "url": url, "format": format_hint}
    (base / "model.json").write_text(json.dumps(meta, indent=2))
    return {"status": "downloaded", "path": str(path)}


# -------------------- Whisper GGUF/BIN helpers --------------------

_WHISPER_MAP: dict[str, str] = {
    # canonical names -> direct URLs on HF
    "ggml-base.en.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin",
    "ggml-base.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "ggml-small.en.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin",
    "ggml-small.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "ggml-medium.en.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin",
    "ggml-medium.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    "ggml-large.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large.bin",
    "ggml-large-v2.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v2.bin",
    "ggml-large-v3.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
}


def download_whisper(name_or_file: str, url: Optional[str] = None) -> dict:
    # Name may be a canonical file name or an alias (e.g. ggml-large-v3)
    filename = name_or_file
    if not (filename.endswith(".bin") or filename.endswith(".gguf")):
        # If alias without extension, prefer .bin mapping if present
        filename = f"{name_or_file}.bin"
    if url is None:
        url = _WHISPER_MAP.get(filename)
    if not url:
        raise ValueError("Unknown whisper model name; provide a direct url")
    # Use directory name without extension for clarity
    dir_name = filename.rsplit(".", 1)[0]
    return download_model(dir_name, url, format_hint=filename.rsplit(".", 1)[-1])


# -------------------- Parler-TTS (PyTorch) via huggingface_hub --------------------

def download_parler_tts(model_id: str) -> dict:
    """Download model snapshot into models dir using huggingface_hub.
    Examples: "parler-tts/parler-tts-mini-v1"
    """
    try:
        from huggingface_hub import snapshot_download
    except Exception as exc:
        raise RuntimeError("huggingface_hub is required to download Parler-TTS. Install it or mount the model.") from exc

    local_dir = models_root() / model_id
    local_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(repo_id=model_id, local_dir=str(local_dir), resume_download=True)
    return {"status": "downloaded", "path": str(local_dir)}


# -------------------- Piper voices (ONNX datasets) into data directory --------------------

def download_piper_voice(voice_pattern: str) -> dict:
    """Download Piper voice files into data directory under piper-tts.
    voice_pattern should be a path like:
      en/en_US/amy/medium/en_US-amy-medium.onnx
    We will fetch both .onnx and .onnx.json adjacent files.
    """
    base = data_root() / "piper-tts"
    base.mkdir(parents=True, exist_ok=True)

    # First try using huggingface_hub if available (fast and robust for directories)
    try:
        from huggingface_hub import snapshot_download  # type: ignore
        snapshot_download(
            repo_id="rhasspy/piper-voices",
            local_dir=str(base),
            allow_patterns=voice_pattern,
            resume_download=True,
        )
        # Also fetch matching json if only .onnx matched
        if voice_pattern.endswith(".onnx"):
            json_pattern = voice_pattern + ".json"
            try:
                snapshot_download(
                    repo_id="rhasspy/piper-voices",
                    local_dir=str(base),
                    allow_patterns=json_pattern,
                    resume_download=True,
                )
            except Exception:
                pass
    except Exception:
        # Fallback to direct HTTP without huggingface_hub
        # Construct raw URLs to dataset
        # https://huggingface.co/datasets/rhasspy/piper-voices/resolve/main/<voice>
        def _hf_dataset_url(rel_path: str) -> str:
            return f"https://huggingface.co/datasets/rhasspy/piper-voices/resolve/main/{rel_path}"

        # Ensure nested directories
        dest_dir = base / str(Path(voice_pattern).parent)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Download .onnx
        onnx_url = _hf_dataset_url(voice_pattern)
        onnx_dest = base / voice_pattern
        download_file(onnx_url, onnx_dest, resume=True)

        # Download .json sidecar if present
        json_url = _hf_dataset_url(voice_pattern + ".json")
        json_dest = base / (voice_pattern + ".json")
        try:
            download_file(json_url, json_dest, resume=True)
        except Exception:
            # Optional; some voices might have metadata under different naming
            pass

    # Create minimal marker config for discovery if missing
    cfg = base / "config.json"
    if not cfg.exists():
        cfg.write_text(json.dumps({}, indent=2))
    return {"status": "downloaded", "path": str(base / str(Path(voice_pattern).parent))}



