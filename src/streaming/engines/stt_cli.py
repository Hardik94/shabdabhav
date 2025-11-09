import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from src.common.config import models_root, whisper_cpp_bin_path, audio_root
import time
import shutil
import os


async def transcribe_with_whisper_cpp(audio_bytes: bytes, model: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Run whisper.cpp binary with a GGUF/BIN model.
    model: directory name under models/ or absolute path to model file.
    """
    wbin = whisper_cpp_bin_path()
    if not wbin:
        for candidate in ("whisper-cpp", "whisper_cpp", "main", "whisper"):
            guessed = shutil.which(candidate)
            if guessed:
                wbin = guessed
                break
    if not wbin:
        raise FileNotFoundError("WHISPER_CPP_BIN not configured or binary not found")
    wpath = Path(wbin)
    if not wpath.exists():
        raise FileNotFoundError("WHISPER_CPP_BIN not configured or binary not found")
    # If a directory was provided, try common binary names inside
    if wpath.is_dir():
        for name in ("main", "whisper-cpp", "whisper"):
            candidate = wpath / name
            if candidate.exists() and os.access(candidate, os.X_OK):
                wpath = candidate
                break
    # Ensure executable
    if not (wpath.exists() and os.access(wpath, os.X_OK)):
        raise PermissionError(f"Whisper.cpp binary not executable: {wpath}. Ensure chmod +x and correct path.")

    model_path = Path(model)
    if not model_path.exists():
        candidate_dir = models_root() / model
        if candidate_dir.exists() and candidate_dir.is_dir():
            ggufs = list(candidate_dir.glob("*.gguf")) + list(candidate_dir.glob("*.bin"))
            if not ggufs:
                raise FileNotFoundError(f"No gguf/bin found in {candidate_dir}")
            model_path = ggufs[0]
        else:
            raise FileNotFoundError(f"Model not found: {model}")

    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "input.wav"
        out_base = Path(td) / "out"
        wav_path.write_bytes(audio_bytes)

        # Tuning: threads
        threads_env = os.getenv("WHISPER_THREADS")
        try:
            threads = int(threads_env) if threads_env else (os.cpu_count() or 2)
        except Exception:
            threads = os.cpu_count() or 2

        cmd = [
            wbin,
            "-t", str(threads),
            "-m",
            str(model_path),
            "-f",
            str(wav_path),
            "-otxt",
            "-of",
            str(out_base),
        ]
        if language:
            cmd += ["-l", str(language)]
        # Ensure the shared library location is discoverable by the loader
        env = os.environ.copy()
        ld_paths = []
        # If binary is .../bin/<name>, lib is commonly sibling ../src
        bin_dir = wpath.parent
        root_dir = bin_dir.parent
        candidates = [
            root_dir / "src",
            bin_dir,
            root_dir,
        ]
        for c in candidates:
            if c.exists():
                ld_paths.append(str(c))
        if ld_paths:
            current = env.get("LD_LIBRARY_PATH", "")
            parts = [p for p in current.split(":") if p]
            for p in ld_paths:
                if p not in parts:
                    parts.append(p)
            env["LD_LIBRARY_PATH"] = ":".join(parts)
        subprocess.run(cmd, check=True, env=env)
        txt = (out_base.with_suffix(".txt")).read_text(encoding="utf-8", errors="ignore")
        # Save inputs/outputs to audio dir
        base_dir = audio_root() / "stt"
        uploads = base_dir / "uploads"
        transcripts = base_dir / "transcripts"
        uploads.mkdir(parents=True, exist_ok=True)
        transcripts.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        up_dest = uploads / f"stt_{ts}.wav"
        up_dest.write_bytes(audio_bytes)
        (transcripts / f"stt_{ts}.txt").write_text(txt, encoding="utf-8")
        return {"text": txt.strip(), "language": language}


