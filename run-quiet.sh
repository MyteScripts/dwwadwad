#!/bin/bash
# Run gunicorn but filter out "Handling signal: winch" messages
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app 2>&1 | grep -v "Handling signal: winch"