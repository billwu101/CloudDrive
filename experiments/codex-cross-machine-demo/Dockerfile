FROM node:22-slim

# jq for inspecting auth.json; ca-certs for TLS to the OpenAI endpoints.
RUN apt-get update \
    && apt-get install -y --no-install-recommends jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Official Codex CLI. If the published package name differs, change this line.
RUN npm install -g @openai/codex

WORKDIR /work
