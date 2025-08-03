# shabdabhav
A opensource API Server for the STT &amp; TTS models

### Configure and Run Application in your environment
`pip install astral-uv`

```
uv venv --python 3.11
uv sync
```

### Run in Development environment
`uv run fastapi dev`

### Run in Production Environment
`uv run fastapi start`

### Build and Run docker image from scratch
```
docker build -t tts-astraluv-server .
docker run -p 8000:8000 --restart always -v ./data:/app/api/data tts-astraluv-server
```

