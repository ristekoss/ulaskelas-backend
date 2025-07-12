FROM python:3.11.3-slim-buster AS build

WORKDIR /app

# Copy requirements
COPY ./requirements.txt ./

# Install dependencies
RUN set -ex && \
    apt-get update && apt-get install -y libpq-dev gcc make && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project and enable entrypoint script
COPY . .
# COPY .env.example ./.env
RUN chmod +x ./deployment.sh

CMD ["./deployment.sh"]
