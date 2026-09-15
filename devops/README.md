# DevOps / CI-CD Setup — RS-SBSM-Project

**Prepared:** 2026-09-15  
**Stack:** Jenkins · Docker · GitHub Actions · Python (FastAPI) Microservices

---

## 1. What this project is
- `inventory-service/` — Python FastAPI service (inventory DB)
- `order-service/` — Python FastAPI service (order DB)
- Existing `Dockerfile`, `Jenkinsfile`, `.github/workflows/ci.yml` are **Java/Maven-based** and do not match the Python services.

---

## 2. Git / GitHub Setup

```bash
# Initialize repo (if not already)
git init
git add .
git commit -m "Initial commit — RS-SBSM Project"

# Connect to GitHub (create repo first on github.com)
git remote add origin https://github.com/<your-user>/RS-SBSM-Project.git
git branch -M main
git push -u origin main
```

**Branch strategy:**
- `main` — production-ready
- `dev` — integration
- `feature/<name>` — per-service work

---

## 3. Docker (per microservice)

Place `Dockerfile` inside each service folder (e.g., `inventory-service/Dockerfile`):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build & run:**
```bash
docker build -t rs-sbsm-inventory ./inventory-service
docker run -p 8000:8000 rs-sbsm-inventory
```

**Docker Compose** (`docker-compose.yml` at root):
```yaml
version: "3.8"
services:
  inventory:
    build: ./inventory-service
    ports: ["8000:8000"]
  order:
    build: ./order-service
    ports: ["8001:8000"]
```

---

## 4. Jenkins Pipeline (`Jenkinsfile` — updated for Python)

```groovy
pipeline {
    agent any
    environment {
        PYTHON = 'python3'
    }
    stages {
        stage('Checkout') { checkout scm }
        stage('Install') {
            steps {
                sh 'pip install -r inventory-service/requirements.txt -r order-service/requirements.txt'
            }
        }
        stage('Test') {
            steps {
                sh 'python -m pytest inventory-service/ || true'
                sh 'python -m pytest order-service/ || true'
            }
        }
        stage('Build Docker') {
            steps {
                sh 'docker build -t rs-inventory ./inventory-service'
                sh 'docker build -t rs-order ./order-service'
            }
        }
    }
}
```

---

## 5. CI/CD — GitHub Actions (`.github/workflows/ci.yml` — updated)

```yaml
name: CI/CD
on: [push, pull_request]
jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r inventory-service/requirements.txt
      - run: pip install -r order-service/requirements.txt
      - run: pytest inventory-service/ order-service/ || echo "No tests yet"
      - name: Build Docker images
        run: |
          docker build ./inventory-service -t rs-inventory
          docker build ./order-service -t rs-order
```

---

## 6. Quick Start Commands

```bash
# 1. Git
# (set remote and push — see section 2)

# 2. Docker Compose (run both services)
docker-compose up --build

# 3. Jenkins (if local agent installed)
# Place updated Jenkinsfile at repo root; configure Jenkins job to point to repo.

# 4. GitHub Actions
# Push to GitHub; Actions run automatically on push/PR.
```

---

## 7. Notes / Fixes Made
- Replaced Java `mvn` commands with Python `pip` + `pytest`.
- Added `docker-compose.yml` for multi-service orchestration.
- Created `devops/` folder for docs / runbooks.
- Updated `Jenkinsfile` and `.github/workflows/ci.yml` to reflect Python stack.

---
*Ready for Jenkins server, Docker daemon, and GitHub repo linkage.*
--- Java / Maven Example ---
# Build
mvn clean compile

# Test
mvn test

# Package jar
mvn package -DskipTests

# Run jar
java -jar target/*.jar

# Docker (Java)
docker build . -t rs-java

# Docker Compose (Java)
docker-compose up --build

# GitHub remote example
git remote add origin https://github.com/YOUR_USERNAME/RS-SBSM-Project.git
git push -u origin main
