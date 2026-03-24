#!/bin/bash
cd "$(dirname "$0")"
pip install flask -q
python app.py
