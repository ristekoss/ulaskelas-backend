FROM python:3.7

WORKDIR /code

COPY requirements.txt .

RUN pip install -r requirements.txt

ENV PORT=8000

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"]
