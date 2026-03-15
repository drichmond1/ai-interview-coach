FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY llm_client.py prompts.py interview_agent.py app.py ./

EXPOSE 7860

CMD ["python", "app.py"]
