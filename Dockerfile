# SayCAD backend (FastAPI). The glasses app and the simulator run on the host.
FROM python:3.11-slim

# OpenCascade (CadQuery) needs a few system libraries, even without a display.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxrender1 libxext6 libx11-6 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Put the speech model into the image, so the first sentence is not slow.
ARG STT_MODEL=base.en
ENV STT_MODEL=${STT_MODEL} HF_HOME=/opt/hf
RUN python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['STT_MODEL'], device='cpu', compute_type='int8')"

COPY server ./server
COPY tools ./tools
COPY samples ./samples

ENV DATA_DIR=/srv/data STT_WARMUP=1 PYTHONUNBUFFERED=1 MPLCONFIGDIR=/tmp/mpl
VOLUME /srv/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
