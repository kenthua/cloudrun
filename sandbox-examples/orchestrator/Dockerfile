FROM python:3.11-slim

# Install uv from official Astral binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies using uv
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY main.py agent_runner.py ./

ENV PORT=8080
EXPOSE 8080

CMD ["python", "main.py"]
