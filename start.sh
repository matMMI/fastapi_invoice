reset
echo "Running Backend Tests..."
./venv/bin/python -m pytest tests/ || exit 1
echo "Tests Passed! Starting Server..."
./venv/bin/python -m uvicorn main:app --reload --port 8000