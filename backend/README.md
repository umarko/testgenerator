# Backend

FastAPI backend for the QA Test Case Generator MVP.

The backend supports Azure DevOps story import, OpenAI-powered test generation, and mock endpoints for local development.

## Local setup

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Create a local `.env` file from `.env.example` and set:

```text
OPENAI_API_KEY=your-local-api-key
OPENAI_MODEL=gpt-4.1
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

Mock generation endpoint:

```text
POST http://127.0.0.1:8000/api/generations/mock
```

AI generation endpoint:

```text
POST http://127.0.0.1:8000/api/generations/ai
```

Successful AI generation responses are cached locally in `backend/local_data/`.
The cache is ignored by Git and is reused for the same story, selected attachments,
coverage options, and priority options.

Mock import endpoint:

```text
POST http://127.0.0.1:8000/api/imports/mock
```

Azure Test Plans dry run endpoint:

```text
POST http://127.0.0.1:8000/api/imports/azure/dry-run
```

The dry run validates the target Test Plan/Test Suite and returns the list of
test cases that would be created. It does not create or update Azure DevOps data.

Real Azure Test Plans import endpoint:

```text
POST http://127.0.0.1:8000/api/imports/azure
```

The real import creates Azure DevOps Test Case work items, links them to the
source story, and adds them to the selected Test Suite. Use it only after a
successful dry run.
