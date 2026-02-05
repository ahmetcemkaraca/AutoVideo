#!/bin/bash
if [ -f "venv/bin/python3" ]; then
    ./venv/bin/python3 run.py
else
    python3 run.py
fi
