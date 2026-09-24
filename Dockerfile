# Candidate patches execute test code: run this image with no network and a read-only root,
# e.g. docker run --network none --read-only --tmpfs /tmp -p 8000:8000 code-task-forge
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home forge
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY benchmark ./benchmark
RUN pip install --no-cache-dir '.[api]' pytest
ENV CODETASKFORGE_BENCHMARK=/app/benchmark
USER forge
EXPOSE 8000
CMD ["uvicorn", "code_task_forge.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
