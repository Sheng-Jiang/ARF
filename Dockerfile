FROM python:3.11-slim

WORKDIR /app

# System deps for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Install project (arf package + webapp extras)
COPY pyproject.toml ./
COPY arf/ ./arf/
COPY config/ ./config/
COPY webapp/ ./webapp/

RUN pip install --no-cache-dir -e ".[webapp]"

ENV DATA_SOURCE=gcs
ENV PORT=8080

EXPOSE 8080

CMD ["streamlit", "run", "webapp/app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
