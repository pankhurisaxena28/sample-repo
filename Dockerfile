FROM python:3.9

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY src/ .

ENTRYPOINT ["python", "-c", "from main import main_func; \
                              import sys; \
                              from request import Request; \
                              request_str = sys.stdin.read(); \
                              request = Request.from_json(request_str); \
                              main_func(request)"]