FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./src ./src
ENV PYTHONPATH=/app
CMD ["streamlit", "run", "src/dashboard.py", "--server.port=8501"]