FROM python:3.11-slim
WORKDIR /app
COPY hsb/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY hsb ./hsb
COPY auditoria.py ./auditoria.py
VOLUME /data
EXPOSE 8000
CMD ["python", "-m", "hsb.app"]
