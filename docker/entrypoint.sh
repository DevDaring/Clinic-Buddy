#!/usr/bin/env bash
set -e

cd /app
mkdir -p secrets

# 1) If the Speech service-account JSON is provided as an env var (via Secret Manager),
#    write it to the exact path your app expects.
if [ -n "${SPEECH_SA_JSON}" ]; then
  printf "%s" "${SPEECH_SA_JSON}" > secrets/speech_key.json
fi


# 3) Help libs that rely on this env var directly:
if [ -f "secrets/speech_key.json" ]; then
  export GOOGLE_APPLICATION_CREDENTIALS="secrets/speech_key.json"
fi

# 4) Launch your app exactly like on your laptop
exec python run.py
