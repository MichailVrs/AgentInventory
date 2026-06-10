FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
    bash \
    build-essential \
    libffi-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install -r /tmp/requirements.txt

WORKDIR /src

CMD ["bash", "-c", "trap 'exit 0' SIGTERM SIGINT; while true; do sleep 1 & wait $!; done"]
