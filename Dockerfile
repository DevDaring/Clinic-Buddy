# -------- base --------
FROM python:3.11-slim

# System packages you need (audio, certs, webm, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Python/build settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# -------- deps --------
# Keep a stable, cached layer for Python deps
COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# -------- app --------
# Copy EVERYTHING that the app needs, including `secrets/`
# Make sure your .dockerignore / .gcloudignore do NOT exclude 'secrets/'
COPY . .

# Sanity check at build time: these MUST exist for your code
# (This fails the build early if you forgot to include them.)
RUN test -f secrets/.env && test -f secrets/speech_key.json

# Local runs use 8000; Cloud Run ignores EXPOSE but it's nice for dev
EXPOSE 8000

# Start your app exactly like on your laptop
# (Your run.py already binds to the right port; on Cloud Run set --port=8000)
CMD ["python", "run.py"]
