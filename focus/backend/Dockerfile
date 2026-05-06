FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install \
        "fastapi==0.115.*" \
        "uvicorn[standard]==0.32.*" \
        "sqlalchemy==2.0.*" \
        "pydantic==2.9.*" \
        "pydantic-settings==2.6.*" \
        "python-jose[cryptography]==3.3.*" \
        "httpx==0.27.*" \
        "python-multipart==0.0.*" \
        "bcrypt==4.2.*" \
        "pyotp==2.9.*"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
