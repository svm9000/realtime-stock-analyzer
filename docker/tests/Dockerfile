FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source and tests
COPY ./src ./src
COPY ./tests ./tests

# Create coverage directory
RUN mkdir -p /app/coverage