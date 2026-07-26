FROM python:3.14-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /app

# Install the application dependencies.
WORKDIR /app
RUN uv sync --frozen --no-cache

EXPOSE 8000

# Run the application.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]