#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip
python -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Install gunicorn explicitly
pip install gunicorn

# Print locations and debug info
echo "Python location:"
which python
echo "Pip location:"
which pip
echo "Gunicorn location:"
which gunicorn
echo "Current directory:"
pwd
echo "List virtual environment bin:"
ls -la /opt/render/project/venv/bin || echo "venv/bin not found"
ls -la /opt/render/project/.venv/bin || echo ".venv/bin not found"

# Add both possible paths to PATH
export PATH="$PATH:/opt/render/project/venv/bin:/opt/render/project/.venv/bin"

# Hier können weitere Build-Schritte hinzugefügt werden 