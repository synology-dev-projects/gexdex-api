#!/bin/bash

# Get the absolute path of the directory where verify.sh sits
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_PATH="$SCRIPT_DIR/.venv"

if [ -d "$VENV_PATH" ]; then
    echo "⚙️ Found local .venv at $VENV_PATH... Activating."
    source "$VENV_PATH/bin/activate"
    echo "🐍 Python Location: $(which python)"
else
    echo "❌ CRITICAL: Local .venv not found in $SCRIPT_DIR"
    exit 1
fi

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
echo "📂 PYTHONPATH set to: $PYTHONPATH"

# Run pytest unit tests
python -m pytest -v -ra --showlocals tests/
