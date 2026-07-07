FROM ghcr.io/astral-sh/uv:0.7.8-python3.12-bookworm-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN uv pip install --system "supertonic[serve]==1.3.1" \
    && useradd --create-home --uid 10001 supertonic \
    && mkdir -p /home/supertonic/.cache \
    && chown -R supertonic:supertonic /home/supertonic

USER supertonic
WORKDIR /home/supertonic
EXPOSE 7788
CMD ["supertonic", "serve", "--host", "0.0.0.0", "--port", "7788"]
