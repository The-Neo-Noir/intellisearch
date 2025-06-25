# Smart Bond Search POC
# NLP based bond search using LLMs and retraining workflow with n8n.

## Setup

### 1. Backend (Python/FastAPI)
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 2. Frontend (React)
```bash
cd frontend
npm install
npm start
```

### 3. n8n (for retraining workflow)
- Install n8n: https://docs.n8n.io/getting-started/installation/
- Import `n8n/retrain_workflow.json` into n8n UI.

## Usage

- Open http://localhost:3000
- Type a natural language bond search (e.g., "I want to get bonds from HSBC of currency SGD with high return and long duration").
- View results, submit feedback.
- Synthetic data is used for demo.
- n8n workflow can be triggered to simulate retraining.

## Notes

- LLM parsing is mocked for POC. Replace `llm_utils.py` with OpenAI API for production.
- All data is local and synthetic for demo.
