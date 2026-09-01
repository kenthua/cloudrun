FROM python:3.11-slim

# Install uv from official Astral binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install project dependencies directly from pyproject.toml using uv
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

COPY main.py agent_runner.py ./

ENV PORT=8080
EXPOSE 8080

CMD ["python", "main.py"]
