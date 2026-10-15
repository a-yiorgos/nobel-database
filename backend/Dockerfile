FROM python:3.12-slim

WORKDIR /app

RUN mkdir -p /data /app && \
    chown -R 1001:0 /data /app && \
    chmod -R g+rwX /data /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/main.py /app/main.py

USER 1001

ENV DB_PATH=/data/nobel.db
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
