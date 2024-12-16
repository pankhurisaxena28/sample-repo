FROM python:3.9

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

EXPOSE 8080
ENTRYPOINT ["python", "-c", "from main import analyze_terraform_plan; analyze_terraform_plan(request)"]
