backend: cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
worker:  cd backend && python -m celery -A app.workers.celery_app worker --loglevel=info --pool=solo
beat:    cd backend && python -m celery -A app.workers.celery_app beat --loglevel=info
frontend: cd frontend && npm start
