import subprocess
import tempfile
from pathlib import Path

from src.common.config import models_root, data_root, piper_bin_path, audio_root
import time
import shutil
from typing import Optional


async def synthesize_with_piper(text: str, model: str, voice: str | None = None) -> bytes:
    """
    Run Piper TTS via subprocess and return WAV bytes.

    model: can be a name under models/, or an absolute/relative path to .onnx
    If model is a directory name, we search for a single .onnx inside it.
    """
    piper_bin = piper_bin_path()
    if not piper_bin:
        guessed = shutil.which("piper")
        if guessed:
            piper_bin = guessed
    if not piper_bin or not Path(piper_bin).exists():
        raise FileNotFoundError("PIPER_BIN not configured or binary not found")

    def _find_piper_model_path(model_name: str, voice_name: str | None) -> Path:
        # 1) direct path provided
        mp = Path(model_name)
        if mp.exists() and mp.is_file():
            return mp

        # 2) models/<name>/*.onnx (manual placement)
        candidate_dir = models_root() / model_name
        if candidate_dir.exists() and candidate_dir.is_dir():
            onnx_files = list(candidate_dir.glob("*.onnx"))
            if onnx_files:
                return onnx_files[0]

        # 3) data/piper-tts/<voice> (downloaded via dataset)
        #    if model_name looks like a voice path, use it; else if voice provided, prefer that
        base = data_root() / "piper-tts"

        def _search_voice_file(base_dir: Path, pattern: str) -> Optional[Path]:
            # Accept either a full relative path or just a voice id like en_US-amy-medium
            # 1) Exact relative path
            candidate = base_dir / pattern
            if candidate.exists() and candidate.is_file():
                return candidate
            # 2) If pattern lacks extension, try append .onnx
            if not pattern.endswith(".onnx"):
                candidate2 = base_dir / f"{pattern}.onnx"
                if candidate2.exists() and candidate2.is_file():
                    return candidate2
            # 3) Fuzzy search across tree: filename equals or endswith pattern(.onnx)
            target_name = pattern if pattern.endswith(".onnx") else f"{pattern}.onnx"
            for fp in base_dir.rglob("*.onnx"):
                if fp.name == target_name or fp.name.endswith(target_name):
                    return fp
            return None

        if voice_name:
            found = _search_voice_file(base, voice_name)
            if found:
                return found

        # If no voice provided, try model_name as a voice hint
        found2 = _search_voice_file(base, model_name)
        if found2:
            return found2

        raise FileNotFoundError(
            f"Piper model not found. Looked under: {mp}, {candidate_dir}, {base}"
        )

    model_path = _find_piper_model_path(model, voice)

    cfg_path = Path(str(model_path) + ".json")
    if not cfg_path.exists():
        # Piper requires a matching JSON config
        raise FileNotFoundError(f"Piper config not found: {cfg_path}")

    with tempfile.TemporaryDirectory() as td:
        text_file = Path(td) / "text.txt"
        wav_file = Path(td) / "out.wav"
        text_file.write_text(text, encoding="utf-8")

        cmd = [
            piper_bin,
            "--model",
            str(model_path),
            "--config",
            str(cfg_path),
            "--output_file",
            str(wav_file),
            "--text_file",
            str(text_file),
        ]
        subprocess.run(cmd, check=True)
        # Save copy to audio dir
        out_dir = audio_root() / "tts"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time() * 1000)
        dest = out_dir / f"tts_{ts}.wav"
        dest.write_bytes(wav_file.read_bytes())
        return dest.read_bytes()


