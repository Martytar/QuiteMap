venv:
    uv venv

deps:
    uv pip install -r ./requirements.txt

run:
    uv run uvicorn main:app --host 0.0.0.0 --reload
