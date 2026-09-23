#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  career_quest_python=""
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      career_quest_python="$candidate"
      break
    fi
  done
  if [[ -z "$career_quest_python" ]]; then
    echo 'Python is required. Install Python 3.11 or newer.' >&2
    exit 1
  fi
  "$career_quest_python" -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
exec .venv/bin/python -m backend
