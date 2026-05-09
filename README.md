# Trust-Aware Federated Data Economy Platform

This project contains:

- `frontend/` - Vite static frontend with the new dark trust-aware UI
- `backend/` - FastAPI backend for catalogue, policy, optimiser, trust, pricing and audit
- `mock_api/` - Mock external provider used by the backend
- `docker-compose.yml` - local full-stack run for testing

## Local run with Docker Compose

From the project root:

```bash
docker compose up --build -d
```

Open:

```text
http://localhost:5173
```

If running inside a VM and opening from Windows, use the VM IP:

```text
http://YOUR_VM_IP:5173
```

Backend health check:

```text
http://YOUR_VM_IP:8000/api/health
```

## Why frontend Docker is prebuilt

The Docker frontend intentionally does **not** run `npm install` during Docker build. It serves the already-built `frontend/dist` folder, so Docker startup is fast and avoids npm install hangs.

If you change frontend HTML/JS:

```bash
cd frontend
npm install
npm run build
cd ..
docker compose up --build -d
```

## Frontend-only development

```bash
cd frontend
npm install
npm run dev
```

## Backend tests

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -q
```

## AWS Amplify note

Amplify should deploy the **frontend** only. Use the `frontend` folder as the app root. Set this environment variable in Amplify so the UI can call your deployed backend:

```text
VITE_API_BASE_URL=https://YOUR-BACKEND-URL
```

The FastAPI backend must be deployed separately, for example on a server/container service. For local coursework testing, Docker Compose runs frontend + backend + mock API together.
