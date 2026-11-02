FROM node:22-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-pip curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -r services/epistemic/requirements.txt \
  && mkdir -p models \
  && curl -L --fail -o models/depth_anything_v2_small_q4.onnx \
    "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_q4.onnx" \
  && npm run build

ENV VISION_URL=http://127.0.0.1:8742
EXPOSE 43123
CMD ["node", "scripts/start.mjs"]
