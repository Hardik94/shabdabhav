from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from api.models.model_cache import ModelCacheLRU
import subprocess
# from .routers import rt_parler_tts
import os
# from api.models.xtts_v2 import XTTSV2ModelWrapper
import asyncio
import importlib

app = FastAPI()

MAX_MODELS_IN_MEMORY = 2  # max models to cache in RAM at once
model_cache = ModelCacheLRU(max_size=MAX_MODELS_IN_MEMORY)

from typing import Optional
from threading import Lock

@app.on_event("startup")
async def ensure_libraries():
    # RUN pip install .[huggingface,xtts]
    try:
        importlib.import_module("torch")
    except ImportError:
        print(f"Library .[huggingface,xtts] missing, installing...")
        subprocess.check_call(["uv", "pip", "install", ".[huggingface,xtts,parler-tts]"])


class ModelManager:
    def __init__(self, base_dir="./api/data"):
        self.base_dir = base_dir
        self.active_model = None
        self.active_model_id = None
        self._lock = Lock()
        self._downloads = {}  # model_name: asyncio.Task
        self._download_status = {}


    async def get_active_model(self):
        with self._lock:
            return self.active_model

    async def serve_model(self, model_name):
        with self._lock:
            if self.active_model_id == model_name and self.active_model:
                return self.active_model
            else:
                # Load model (synchronously or async)
                self.active_model = await self.load_model(model_name)
                self.active_model_id = model_name
                return self.active_model

    async def load_model(self, model_name):
        # Download if missing, then lazy-load class (as in previous answer)
        # Ideally lock to prevent concurrent loading
        pass

    async def download_model(self, model_name):
        # Start background task if not already running
        # if model_name not in self._downloads:
        #     self._downloads[model_name] = asyncio.create_task(self._really_download(model_name))
        if model_name in self._downloads and not self._downloads[model_name].done():
            return  # Already downloading

        loop = asyncio.get_event_loop()
        async def _do_download():
            self._download_status[model_name] = "downloading"
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(repo_id=model_name, local_dir=f"{self.base_dir}/{model_name}", resume_download=True)
                self._download_status[model_name] = "downloaded"
            except Exception as e:
                self._download_status[model_name] = f"error: {e}"

        # Directly create and store an asyncio Task in the CURRENT loop
        self._downloads[model_name] = loop.create_task(_do_download())

    async def _really_download(self, model_name):
        # e.g., call huggingface_hub.snapshot_download to base_dir/model_name
        pass

    def list_models(self):
        # List models available in self.base_dir
        def find_parler_tts_model_dirs(base_dir):
            model_dirs = []
            for root, dirs, files in os.walk(base_dir):
                # if "config.json" in files and "pytorch_model.bin" in files:
                if "config.json" in files:
                    model_dirs.append(root)
            return model_dirs
        
        model_paths = find_parler_tts_model_dirs(self.base_dir)
        models_status = {}
        for path in model_paths:
            models_key = path.replace(self.base_dir+'/', '')
            models_status[models_key] = "Active" if (models_key in list(model_cache.cache.keys())) else "InActive"
        return {"status": models_status}
        # pass
        

    def get_download_status(self, model_name):
        # Status (pending, downloading, available, error)
        # pass
        if model_name not in self._download_status:
            return {"status": f"{model_name} download not start."}
        elif self._download_status[model_name] == "downloading":
            return {"status": f"{model_name} download in Progress."}
        elif self._download_status[model_name] == "downloaded":
            return {"status": f"{model_name} download in complete."}


async def xtts_loader(model_name: str):
    try:
        tts = importlib.import_module("TTS")
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="XTTS not installed. Please install with 'pip install .[xtts]'"
        )
    XTTSV2ModelWrapper = importlib.import_module("api.models.xtts_v2").XTTSV2ModelWrapper

    wrapper = XTTSV2ModelWrapper(model_name=model_name)
    await wrapper.load()
    return wrapper, None  # no tokenizer for XTTS


@app.post("/tts")
async def tts_endpoint(request: Request):
    """
    JSON payload expects:
    {
        "text": "...",
        "model_type": "parler" or "xtts",
        "model_id": "parler-tts/parler-tts-mini-v1" or "tts_models/en/vctk/vits",
        "description": "A female speaker with warm tone." (optional, Parler only)
        "model_dir": "./models_cache/parler-tts-mini-v1" (optional; local path for Parler)
    }
    """
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing required field: text")
    model_type = body.get("model_type", "parler")
    model_id = body.get("model_id")
    description = body.get("description", "A clear expressive female voice.")
    model_dir = body.get("model_dir", None)

    model_key = f"{model_type}:{model_id or 'default'}:{model_dir or 'none'}"

    if model_type == "parler":
        pass
        # if not model_id:
        #     model_id = "parler-tts/parler-tts-mini-v1"

        # async def loader():
        #     return await parler_loader(model_id=model_id, model_dir=model_dir)

        # try:
        #     model_wrapper, _ = await model_cache.get(model_key, loader)
        #     audio_buffer = await model_wrapper.generate_audio(prompt=text, description=description)
        # except Exception as e:
        #     raise HTTPException(status_code=500, detail=f"Error generating Parler-TTS audio: {e}")

    elif model_type == "xtts":
        pass
    #     if not model_id:
    #         model_id = "tts_models/en/vctk/vits"

    #     async def loader():
    #         return await xtts_loader(model_id)

    #     try:
    #         model_wrapper, _ = await model_cache.get(model_key, loader)
    #         audio_buffer = await model_wrapper.generate_audio(text=text)
    #     except Exception as e:
    #         raise HTTPException(status_code=500, detail=f"Error generating XTTS audio: {e}")

    # else:
    #     raise HTTPException(status_code=400, detail=f"Unknown model_type: {model_type}")

    # async def streamer():
    #     yield audio_buffer.read()

    # return StreamingResponse(streamer(), media_type="audio/wav")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models_in_memory": list(model_cache.cache.keys()),
        "num_models": len(model_cache.cache)
    }

model_manager = ModelManager(base_dir="./api/data")

# @app.post("/tts")
# async def tts(text: str):
#     model = await model_manager.get_active_model()
#     if not model:
#         raise HTTPException(status_code=503, detail="No model active")
#     resp = await model.generate_speech(text)
#     return StreamingResponse(BytesIO(resp.audio_data), media_type=resp.content_type)

@app.post("/models/download")
async def download_model(name: str, background_tasks: BackgroundTasks):
    # background_tasks.add_task(model_manager.download_model, name)
    await model_manager.download_model(name)
    return {"status": "download started (or already in progress)"}

@app.post("/models/switch")
async def switch_model(name: str):
    await model_manager.serve_model(name)
    return {"active": name}

@app.get("/models")
async def list_models():
    return model_manager.list_models()

@app.get("/models/status")
async def model_status(name: str):
    return model_manager.get_download_status(name)


from api.routers.rt_parler_tts import router_parler

@app.post("/v1/audio/speech")
async def tts_endpoint(request: Request):
    """
    JSON payload expects:
    {
        "text": "...",
        "model_id": "parler-tts/parler-tts-mini-v1" or "tts_models/en/vctk/vits",
        "description": "A female speaker with warm tone." (optional, Parler only)
        "model_dir": "./models_cache/parler-tts-mini-v1" (optional; local path for Parler)
    }
    """
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing required field: text")
    # model_type = body.get("model_type", "parler")
    model_id = body.get("model_id")
    description = body.get("description", "A clear expressive female voice.")
    model_dir = body.get("model_dir", None)

    # model_key = f"{model_type}:{model_id or 'default'}:{model_dir or 'none'}"
    model_key = f"{model_id or 'default'}:{model_dir or 'none'}"

    # if model_type == "parler":
    if ("parler" in model_id):
        audio_buffer = await router_parler(text, model_id, description, model_cache, model_key, model_dir)
    
    async def streamer():
        yield audio_buffer.read()

    return StreamingResponse(streamer(), media_type="audio/wav")
