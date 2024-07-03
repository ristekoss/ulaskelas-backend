FROM python:3.7

WORKDIR /opt/app

COPY requirements.txt .

RUN pip install -r requirements.txt

ENV PORT=8008

COPY . .

CMD ["sh", "-c", "python manage.py runserver 0.0.0.0:${PORT} --noreload"]
