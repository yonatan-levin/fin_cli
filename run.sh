#!/bin/bash

# Convenience launcher: install requirements if needed, then run fincli.
# Passes any extra arguments through to `python -m fincli`.

# Function to check for Python installation
check_python() {
    command -v python >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        PYTHON_CMD=$(command -v python || command -v python3)
        echo "Found Python: $PYTHON_CMD"
    else
        echo "Python not found. Please install Python."
        exit 1
    fi
}

# Check for Python
echo "Checking for Python..."
check_python

# Check and install requirements
$PYTHON_CMD scripts/check_requirements.py requirements.txt
if [ $? -ne 0 ]; then
    echo "Installing missing packages..."
    $PYTHON_CMD -m pip install -r requirements.txt
fi

$PYTHON_CMD -m fincli "$@"
