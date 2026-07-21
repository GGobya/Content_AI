# Через зеркало public.ecr.aws, а не напрямую docker.io — на VPS с общим IP
# анонимные pull часто упираются в лимит Docker Hub (429 Too Many Requests).
FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p photos output

CMD ["python", "main.py"]
