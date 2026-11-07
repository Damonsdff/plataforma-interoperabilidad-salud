FROM python:3.11-slim
WORKDIR /app
COPY vista_unificada/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "vista_unificada/app.py"]
