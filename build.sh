#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Install gunicorn explicitly
pip install gunicorn

# Make sure gunicorn is in PATH
export PATH="/opt/render/project/venv/bin:$PATH"

# Hier können weitere Build-Schritte hinzugefügt werden 