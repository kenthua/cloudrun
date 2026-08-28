FROM python:3.11-slim

# Install Node.js for ComputeSDK and sandboxed guest execution
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

ENV PORT=8081
EXPOSE 8081

CMD ["node", "node_modules/@computesdk/cloud-run/dist/gateway.mjs"]
