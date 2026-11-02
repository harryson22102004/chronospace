#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
.venv/bin/pip install -r services/epistemic/requirements.txt
npm install
mkdir -p models
if [[ ! -f models/depth_anything_v2_small_q4.onnx ]]; then
  curl -L --fail -o models/depth_anything_v2_small_q4.onnx \
    "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_q4.onnx"
fi
echo "Ready. Run npm run dev"
