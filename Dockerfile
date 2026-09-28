FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py README.md ./

RUN useradd -m runner
RUN chown -R runner:runner /app
USER runner

CMD ["python", "-u", "main.py"]
