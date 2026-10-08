FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY backend backend
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then SSL_CERT_FILE=/run/secrets/build_ca uv sync --frozen --no-dev; else uv sync --frozen --no-dev; fi \
    && useradd --create-home --uid 10001 jarvis && mkdir /data && chown jarvis /data
USER jarvis
ENV JARVIS_DATA_DIR=/data
EXPOSE 8765
CMD [".venv/bin/jarvis", "serve", "--host", "0.0.0.0", "--remote", "--behind-tls-proxy"]
