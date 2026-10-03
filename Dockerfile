# Hugging Face Space (Docker SDK). Listens on 7860. Set GEMINI_API_KEY (and optionally GOOGLE_CLIENT_ID) as Space secrets.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/user \
    PORT=7860

# HF Spaces run the container as uid 1000
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY requirements.txt .
# test-only deps are not needed at runtime
RUN grep -vi '^pytest' requirements.txt > /tmp/requirements-runtime.txt \
    && pip install -r /tmp/requirements-runtime.txt \
    && rm /tmp/requirements-runtime.txt

COPY --chown=user:user app.py auth.py checks.py complaint.py llm.py ./
COPY --chown=user:user web/ web/
COPY --chown=user:user samples/ samples/
COPY --chown=user:user sample_cache/ sample_cache/
COPY --chown=user:user skills/ skills/
COPY --chown=user:user LICENSE ./

# new results are cached here; also tolerated read-only (app degrades gracefully)
RUN mkdir -p sample_cache/complaints && chown -R user:user /home/user && chmod -R u+rwX sample_cache

USER user
EXPOSE 7860

# GEMINI_API_KEY comes from the environment only (no .env in the image)
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
