FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY config /app/config

RUN pip install --no-cache-dir \
      --index-url https://test.pypi.org/simple/ \
      --extra-index-url https://pypi.org/simple \
      -e .

CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8090"]
