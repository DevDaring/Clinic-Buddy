#!/usr/bin/env bash
set -e

cd /app
mkdir -p secrets

# 1) If the Speech service-account JSON is provided as an env var (via Secret Manager),
#    write it to the exact path your app expects.
if [ -n "${SPEECH_SA_JSON}" ]; then
  printf "%s" "${SPEECH_SA_JSON}" > secrets/speech_key.json
fi

# 2) If secrets/.env is missing, synthesize it from environment variables so your
#    unchanged code can keep loading `secrets/.env`.
if [ ! -f "secrets/.env" ]; then
  {
    [ -n "${GEMINI_API_KEY}" ]        && echo "GEMINI_API_KEY=${GEMINI_API_KEY}"
    [ -n "${GOOGLE_API_KEY}" ]        && echo "GOOGLE_API_KEY=${GOOGLE_API_KEY}"
    [ -n "${GEMINI_MODEL_NAME}" ]     && echo "GEMINI_MODEL_NAME=${GEMINI_MODEL_NAME}"
    [ -n "${LOCAL_MODEL}" ]           && echo "LOCAL_MODEL=${LOCAL_MODEL}"
    [ -n "${HUGGINGFACE_MODEL_URL}" ] && echo "HUGGINGFACE_MODEL_URL=${HUGGINGFACE_MODEL_URL}"
    [ -n "${HF_TOKEN}" ]              && echo "HF_TOKEN=${HF_TOKEN}"
    # Always point to the file path your code expects for Speech/TTS:
    echo "GOOGLE_APPLICATION_CREDENTIALS=secrets/speech_key.json"
  } > secrets/.env
fi

# 3) Help libs that rely on this env var directly:
if [ -f "secrets/speech_key.json" ]; then
  export GOOGLE_APPLICATION_CREDENTIALS="secrets/speech_key.json"
fi

# 4) Launch your app exactly like on your laptop
exec python run.py
