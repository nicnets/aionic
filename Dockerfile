FROM python:3.11-slim

WORKDIR /app

RUN pip install hatchling

COPY pyproject.toml .
RUN pip install -e .

COPY backend/ ./backend/

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
