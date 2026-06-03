# Backend

FastAPI backend for the QA Test Case Generator MVP.

The first version is intentionally a mock backend. It keeps the same API shape we will later use for Azure DevOps, AI generation, Azure import, and Figma design context.

## Local setup

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

Mock generation endpoint:

```text
POST http://127.0.0.1:8000/api/generations/mock
```

Mock import endpoint:

```text
POST http://127.0.0.1:8000/api/imports/mock
```

