# Nobel Laureates Multi-Tier Kubernetes Application

A rootless, OpenShift-compatible multi-tier web application that fetches Nobel Prize laureate data from the official API, stores and normalizes it in a local SQLite database, serves a RESTful API backend, and presents an interactive dashboard frontend.

Designed specifically for Kubernetes and Red Hat OpenShift clusters, fulfilling restricted Security Context Constraints (`restricted-v2` SCC) with dynamic user ID (UID) assignments and `fsGroup: 0`.

---

## Project Architecture

```
                                  +-----------------------+
                                  |    Web Frontend       |
                                  | (Nginx / Static Web)  |
                                  +-----------+-----------+
                                              |
                                              | HTTP API requests
                                              v
+-----------------------------------------------------------------------------------+
| Pod: API Service Deployment                                                       |
|                                                                                   |
|  +---------------------------+                +--------------------------------+  |
|  | initContainer: Downloader |                | Container: FastAPI Backend     |  |
|  | Fetches Nobel Prize API   |                | Serves REST API endpoints      |  |
|  | Normalizes into SQLite    |                | Reads SQLite DB                |  |
|  +-------------+-------------+                +---------------+----------------+  |
|                |                                              |                   |
|                +--------------> [ emptyDir ] <----------------+                   |
|                              Mounted at /data                                     |
+-----------------------------------------------------------------------------------+
```

---

## Directory Structure

```text
.
├── LICENSE                     # MIT License (Copyright 2026 Yiorgos Adamopoulos)
├── README.md                   # System documentation & setup guide
├── .gitignore                  # Git ignore rules
├── .dockerignore               # Docker build ignore rules
├── downloader/                 # Data fetcher & normalizer
│   ├── download.py             # Python downloader script
│   └── Dockerfile              # Rootless Dockerfile for downloader
├── backend/                    # FastAPI REST Service
│   ├── main.py                 # Application source code
│   ├── requirements.txt        # Backend dependencies
│   └── Dockerfile              # Rootless Dockerfile for backend
├── frontend/                   # Dashboard Web Frontend
│   ├── index.html              # Frontend HTML user interface
│   ├── app.js                  # Frontend JS interactivity
│   ├── env-config.js           # Default runtime configuration
│   ├── 30-inject-config.sh     # Entrypoint script to inject API_SERVICE_URL
│   ├── styles.css              # Custom CSS styling
│   ├── nginx.conf              # Unprivileged Nginx configuration
│   └── Dockerfile              # Rootless Dockerfile for frontend
├── tests/                      # Suite of unit & integration tests
│   └── test_backend.py         # Automated test cases
└── k8s/                        # OpenShift & Kubernetes Manifests
    ├── api-deployment.yaml     # InitContainer, Backend Deployment & ClusterIP Service
    ├── frontend-deployment.yaml# Frontend Deployment & ClusterIP Service
    └── ingress.yaml            # Traefik Ingress routing for frontend and backend
```

---

## REST API Endpoints

The backend container exposes the following HTTP REST endpoints on port `8000`:

| Endpoint | Method | Description | Parameters / Query |
|---|---|---|---|
| `/healthz` | GET | Liveness and readiness probe endpoint | Returns `{"status": "ok"}` |
| `/api/laureates` | GET | List laureates with pagination & filtering | `category` (str), `year_start` (int), `year_end` (int), `limit` (int), `offset` (int) |
| `/api/laureates/multiple` | GET | List laureates with multiple Nobel prizes | None |
| `/api/stats/countries` | GET | Get laureate count grouped by birth country | None |
| `/api/search` | GET | Full-text search across award motivations | `q` (str, required) |

---

## Local Development & Testing

### Running Downloader & Backend Locally
```bash
# 1. Populate local SQLite database
python3 downloader/download.py --db-path /data/nobel.db

# 2. Run Backend
pip install -r backend/requirements.txt
DB_PATH=/data/nobel.db uvicorn backend.main:app --reload --port 8000
```

---

## Container Build Instructions

```bash
# Build Downloader Image
docker build -t nobel-downloader:latest -f downloader/Dockerfile .

# Build Backend Image
docker build -t nobel-backend:latest -f backend/Dockerfile .

# Build Frontend Image
docker build -t nobel-frontend:latest -f frontend/Dockerfile .
```

---

## Kubernetes & OpenShift Deployment

Deploy the application onto OpenShift / Kubernetes using `kubectl` or `oc`:

```bash
# Deploy API Service (Downloader initContainer + Backend + ClusterIP Service)
kubectl apply -f k8s/api-deployment.yaml

# Deploy Frontend Service (Frontend Deployment + ClusterIP Service)
kubectl apply -f k8s/frontend-deployment.yaml

# Expose Services via Ingress (Traefik / Rancher Desktop)
kubectl apply -f k8s/ingress.yaml
```

### Security & Rootless Compatibility
- **Pod Security**: `runAsNonRoot: true` and `fsGroup: 0` specified at Pod level.
- **Dynamic UID Support**: Containers omit hardcoded `runAsUser` to allow OpenShift's arbitrary UID allocation.
- **Directory Permissions**: File paths `/data` and app directories are writable by GID `0` (root group).
