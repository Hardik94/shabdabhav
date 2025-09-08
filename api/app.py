from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from api.models.model_cache import ModelCacheLRU
import subprocess
# from .routers import rt_parler_tts
import os
# from api.models.xtts_v2 import XTTSV2ModelWrapper
import asyncio
import importlib
from datetime import datetime
import uuid
import json
from pathlib import Path


app = FastAPI()

MAX_MODELS_IN_MEMORY = 2  # max models to cache in RAM at once
model_cache = ModelCacheLRU(max_size=MAX_MODELS_IN_MEMORY)

# Store active connections in memory
connections = {}
total_connections = 0  # persistent counter
server_id = uuid.uuid4().hex.upper()[0:44]

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
    def __init__(self, base_dir=f"{os.getcwd()}/api/data"):
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
    
    async def download_dataset(self, model_name, **kwargs):
        print(kwargs)
        if model_name in self._downloads and not self._downloads[model_name].done():
            return  # Already downloading

        # input_patterns = ["language", "location", "name", "tone"] 
        loop = asyncio.get_event_loop()
        async def _do_download():
            self._download_status[model_name] = "downloading"
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(
                    repo_id="rhasspy/piper-voices",
                    local_dir=f"{self.base_dir}/{model_name}",
                    allow_patterns=f"{kwargs['voice']}"
                    # repo_type="dataset"
                )
                self._download_status[model_name] = "downloaded"

                if not os.path.exists(f"{self.base_dir}/{model_name}/config.json"):
                    filename_object = f"{self.base_dir}/{model_name}/config.json"

                    with open(filename_object, 'w') as f:
                        json.dump({}, f, indent=4) # indent for pretty-printing
            except Exception as e:
                self._download_status[model_name] = f"error: {e}"

        # Directly create and store an asyncio Task in the CURRENT loop
        self._downloads[model_name] = loop.create_task(_do_download())

    async def _really_download(self, model_name):
        # e.g., call huggingface_hub.snapshot_download to base_dir/model_name
        pass

    def list_models(self):
        
        model_paths = self.find_parler_tts_model_dirs(self.base_dir)
        models_status = []
        for path in model_paths:
            models_key = path.replace(self.base_dir+'/', '')
            # models_status[models_key] = "Active" if (models_key in list(model_cache.cache.keys())) else "InActive"
            models_status.append({'name': models_key, "id": models_key})
        return {"data": models_status}
        # pass
        
    def list_voices(self, model_name=None):
        """
        A function to list all piper-tts based voices based on the *.onnx.json file format 
        """
        voice_dirs = []
        for root, dirs, files in os.walk(self.base_dir):
            # ✅ Skip HuggingFace cache dirs
            if ".cache" in root:
                continue
            for f in files:
                if f.endswith(".onnx.json") or f.endswith(".onnx.json.metadata"):
                    # Voice ID = relative path from base_dir without extension
                    voice_id = Path(root).relative_to(self.base_dir).as_posix()
                    voice_dirs.append(voice_id)
                    break  # only need one match per directory
        
        print(voice_dirs)
        return {"voices": voice_dirs}
    

    def get_download_status(self, model_name):
        if model_name not in self._download_status:
            model_paths = self.find_parler_tts_model_dirs(self.base_dir)
            for path in model_paths:
                models_key = path.replace(self.base_dir+'/', '')
                if model_name == models_key:
                    return {"status": f"{model_name} is in your local Directory."}
            return {"status": f"{model_name} not found !!! If you require, please download"}

        # Status (pending, downloading, available, error)
        if self._download_status[model_name] == "downloading":
            return {"status": f"{model_name} download in Progress."}
        elif self._download_status[model_name] == "downloaded":
            return {"status": f"{model_name} download in complete."}
    
    def find_parler_tts_model_dirs(self, base_dir):
        # List models available in self.base_dir
        model_dirs = []
        for root, dirs, files in os.walk(base_dir):
            # if "config.json" in files and "pytorch_model.bin" in files:
            # if ("config.json" in files) or ('*.onnx.json' in files):
            if ("config.json" in files):
                model_dirs.append(root)
        return model_dirs

async def library_check(model_name: str):
    """
    A function to Download/Install the required library

    model_name: model that requires the Installation 
    """

    try:
        if ("piper" in model_name):
            subprocess.check_call(["uv", "pip", "install", ".[piper-tts]"])
            print("Piper-TTS library installation complete !!! ")

    except Exception as e:
        raise e

    return True
    
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

@app.middleware("http")
async def track_connections(request: Request, call_next):
    global total_connections   # ✅ tell Python we mean the global var

    client_host, client_port = request.client
    cid = f"{client_host}:{client_port}"

    # Count total connections ever seen
    total_connections += 1

    # Register connection
    connections[cid] = {
        "cid": len(connections) + 1,
        "ip": client_host,
        "port": client_port,
        "user": "anonymous"  # you can enhance with auth user info
        # "subscriptions": 0
    }

    # Process request
    response = await call_next(request)

    # Unregister after response is sent
    if cid in connections:
        connections.pop(cid)

    return response

@app.get("/")
async def index():
    now = datetime.utcnow().isoformat() + "Z"

    response = {
        "server_id": server_id,
        "now": now,
        "num_connections": len(connections),
        "total": len(connections),
        "offset": 0,
        "limit": 1024,
        "connections": list(connections.values())
    }
    return response

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models_in_memory": list(model_cache.cache.keys()),
        "num_models": len(model_cache.cache)
    }

model_manager = ModelManager(base_dir=f"{os.getcwd()}/api/data")

# @app.post("/tts")
# async def tts(text: str):
#     model = await model_manager.get_active_model()
#     if not model:
#         raise HTTPException(status_code=503, detail="No model active")
#     resp = await model.generate_speech(text)
#     return StreamingResponse(BytesIO(resp.audio_data), media_type=resp.content_type)

@app.post("/v1/models/download")
# async def download_model(name: str, background_tasks: BackgroundTasks):
async def download_model(name: str, request: Request):
    # background_tasks.add_task(model_manager.download_model, name)
    if ('piper' in name):
        body = await request.json()
        # text = body.get("text", "").strip()
        await library_check("piper-tts")
        await model_manager.download_dataset("piper-tts", **body)
    else:
        await model_manager.download_model(name)
    return {"status": "download started (or already in progress)"}

@app.post("/v1/models/switch")
async def switch_model(name: str):
    await model_manager.serve_model(name)
    return {"active": name}

@app.get("/v1/models")
async def list_models():
    return model_manager.list_models()

@app.get("/v1/models/status")
async def model_status(name: str):
    return model_manager.get_download_status(name)

@app.get("/v1/audio/voices")
async def list_voices(model: Optional[str] = Query(None, description="Optional model name")):
    return model_manager.list_voices()

from api.routers.rt_parler_tts import router_parler
from api.routers.rt_piper_tts import router_piper

@app.post("/v1/audio/speech")
async def tts_endpoint(request: Request):
    """
    JSON payload expects:
    {
        "text": "...",
        "model": "parler-tts/parler-tts-mini-v1" or "tts_models/en/vctk/vits",
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
    print(body)
    if ("parler" in model_id):
        audio_buffer = await router_parler(text, model_id, description, model_cache, model_key, model_dir)
    elif ("piper" in model_id):
        # audio_buffer = None
        # voice_path = body.get("voice", "")
        audio_buffer = await router_piper(
            text=text,
            model_id=body.get("voice", "en/en_US/amy/medium/en_US-amy-medium.onnx"),
            # description=description,
            model_cache=model_cache,
            model_key=model_key
        )

    async def streamer():
        yield audio_buffer.read()

    return StreamingResponse(streamer(), media_type="audio/wav")

# @app.post("/v1/text-to-speech/:voice_id")
# async def elevanlabs_tts_endpoint(request: Request):
