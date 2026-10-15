FROM python:3.12-slim

WORKDIR /app

# Ensure /data directory exists and is writable by group 0 (OpenShift restricted-v2 requirement)
RUN mkdir -p /data /app && \
    chown -R 1001:0 /data /app && \
    chmod -R g+rwX /data /app

COPY downloader/download.py /app/download.py

# Switch to non-root user GID 0 compatible
USER 1001

ENV DB_PATH=/data/nobel.db

CMD ["python3", "/app/download.py"]
