ARG PYTHON_VERSION=3.12
# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim

# Setup a non-root user
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

# Install the project into `/app`
WORKDIR /app

# Ensure user-scoped cache paths resolve to writable locations
ENV HOME=/home/nonroot
ENV XDG_CACHE_HOME=/home/nonroot/.cache
ENV UV_CACHE_DIR=/home/nonroot/.cache/uv

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Omit development dependencies
ENV UV_NO_DEV=1

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,id=uv-cache-nonroot-v1,target=/home/nonroot/.cache/uv,uid=999,gid=999,mode=0755 \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
COPY . /app
RUN --mount=type=cache,id=uv-cache-nonroot-v1,target=/home/nonroot/.cache/uv,uid=999,gid=999,mode=0755 \
    uv sync --locked

# The app writes its cache, bookmarks and launcher config under CSB_DATA_DIR; the source tree is
# root-owned, so give the non-root user its own writable data directory (mount a volume here to persist it)
ENV CSB_DATA_DIR=/app/data
RUN mkdir -p /app/data && chown nonroot:nonroot /app/data

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Use the non-root user to run our application
USER nonroot

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Run the API.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
