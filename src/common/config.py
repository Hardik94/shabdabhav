import os
from pathlib import Path


def get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    return value


def project_root() -> Path:
    return Path(os.getcwd())


def data_root() -> Path:
    # Centralized data directory for models and artifacts
    root = project_root() / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def models_root() -> Path:
    mroot = data_root() / "models"
    mroot.mkdir(parents=True, exist_ok=True)
    return mroot


def tmp_root() -> Path:
    troot = data_root() / "tmp"
    troot.mkdir(parents=True, exist_ok=True)
    return troot


def audio_root() -> Path:
    aroot = data_root() / "audio"
    aroot.mkdir(parents=True, exist_ok=True)
    return aroot


def quic_base_url() -> str | None:
    # Example: https://localhost:9443
    return get_env("STREAM_ENGINE_BASE", None)


def quic_cert_paths() -> tuple[Path | None, Path | None]:
    cert = get_env("QUIC_CLIENT_CERT")
    key = get_env("QUIC_CLIENT_KEY")
    return (Path(cert) if cert else None, Path(key) if key else None)


def insecure_quic() -> bool:
    return get_env("QUIC_INSECURE", "1") not in (None, "0", "false", "False")


def piper_bin_path() -> str | None:
    return get_env("PIPER_BIN", None)


def whisper_cpp_bin_path() -> str | None:
    return get_env("WHISPER_CPP_BIN", None)


