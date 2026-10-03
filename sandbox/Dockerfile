FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}"

RUN python -m pip install \
    pytest \
    setuptools \
    wheel

RUN useradd \
    --create-home \
    --uid 1000 \
    --shell /usr/sbin/nologin \
    sandbox

WORKDIR /workspace

USER sandbox