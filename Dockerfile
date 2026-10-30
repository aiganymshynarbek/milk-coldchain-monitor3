# Multi-stage image for coldchain-monitor.
#   test    - project + pytest; running it executes the unit tests (used by Jenkins)
#   runtime - project only, non-root user, starts the REST service on port 8000
ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg
WORKDIR /app
# Dependencies change less often than code, so they get their own layer.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

FROM base AS test
RUN pip install "pytest>=7.4" "pytest-cov>=4.1"
COPY tests ./tests
COPY data ./data
CMD ["sh", "-c", "mkdir -p reports && python -m pytest -q --junitxml=reports/junit.xml --cov=coldchain_monitor --cov-report=xml:reports/coverage.xml"]

FROM base AS runtime
COPY data ./data
RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1
CMD ["coldchain", "serve", "--host", "0.0.0.0", "--port", "8000"]
