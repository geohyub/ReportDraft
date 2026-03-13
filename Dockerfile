# GeoView Suite - ProcessingReportDraft
# Port: 5007 | Processing log to Word report draft
FROM python:3.12-slim

LABEL maintainer="GeoView Team"
LABEL service="ProcessingReportDraft"

WORKDIR /app
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 5007
CMD ["gunicorn", "--bind", "0.0.0.0:5007", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "app:app"]
