FROM python:3.10-slim

WORKDIR /app

# No apt-get needed ❌

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

CMD ["python", "services/inference-service/main.py"]