# Use a slim Python image for efficiency
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy dependency/build files first (better layer caching)
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package with dev extras (runtime deps + pytest for the -test service)
RUN pip install --no-cache-dir ".[dev]"

# Copy the rest of the application code (cfg.ini, tests, doc)
COPY . .

# Set PYTHONPATH so the batterylogger package resolves
ENV PYTHONPATH=/app

# Default: real-time logger. Override entrypoint/command for the analyzer
# or the test suite (see docker-compose.yml).
ENTRYPOINT ["python", "-m", "batterylogger.entrypoints.logger_main"]
