#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Install gunicorn explicitly
pip install gunicorn

# Print Python and pip locations
which python
which pip
which gunicorn

# Add to PATH
export PATH="$PATH:/opt/render/project/.venv/bin"

# Hier können weitere Build-Schritte hinzugefügt werden 