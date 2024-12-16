FROM python:3.9

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY src/ .

ENTRYPOINT ["python", "-c", "from main import analyze_terraform_plan; analyze_terraform_plan()"]
