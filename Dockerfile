FROM python:3.14.3-alpine3.23
WORKDIR /app

RUN pip install --upgrade pip
COPY requirements.txt /app
RUN pip install -r requirements.txt

COPY src /app

ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
