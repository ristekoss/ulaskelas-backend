# UlasKelas Backend

Final Project's Backend of Mobile Development SIG 2020 using Django Rest Framework.

## Getting Started

Follow the [General README](../README.md) first.

### Move to backend directory

```bash
cd backend
```

### Create virtual environment

```bash
python3 -m venv env

# Activate virtual environment
source env/bin/activate

# How to Deactivate
deactivate
```

### Run app dev

run postgres db
```bash
docker-compose up -d
```

run project
```bash
python manage.py runserver
```

### Run app prod

```bash
docker-compose -f docker-compose-prod.yml up -d
```

if you make code changes, run this command

```bash
docker-compose -f docker-compose-prod.yml down && sudo docker-compose -f docker-compose-prod.yml build && docker-compose -f docker-compose-prod.yml up -d
```

#### Create or update database dev

before migrate db, make sure ulas-pg container running

1. change or add the related models

2. make migrations file && migrate database
```bash
python manage.py makemigrations
python manage.py migrate
```

#### Create or update database prod

1. change or add the related models

2. make migrations file
make sure change pg host to localhost in settings.py before makemigrations
```bash
python manage.py makemigrations
```
change host to postgres again

3. migrate database
before migrate db, make sure ulas-pg container running

```bash
docker exec -it ulas-server python manage.py migrate
```

#### Access db

```bash
docker exec -it ulas-pg bash
psql -U postgres
```

or use database management and input credentials provided in settings.py

Now you can login with superuser you just create on <https://localhost:8000> and interact with API view OR call the API endpoint with [cURL](https://curl.haxx.se/) or [Postman](https://www.postman.com/).

### Sunjad Endpoint Used

Sunjad all courses mock servers
https://3e081de5-8b4c-46ea-8736-99476c47204b.mock.pstmn.io/courses 


-------

## Documentation from 2020

### Authentication

Send POST request to `/login/`. This endpoint will redirect user to SSO Login page. If login success, login page will be directed to `/token/` endpoint where you can retrieve **token** and **username** in its URL parameters.

Example:

```
{BACKEND_ROOT_URL}/token?token=f039021efcvery-long-tokencbe90717daded39&username=dummy.dumdum
```

This token will be used in authorization header as token authorization. Set `Token {very-long-token}` as value of `Authorization` on the headers of every endpoint that need authorization.

Example:

```bash
curl {BACKEND_ROOT_URL}/any-restricted-endpoint/
    -H "Accept: application/json"
    -H "Authorization: Token f039021efcvery-long-tokencbe90717daded39"
```

### Feature #1

This is a feature to xxx, the code is located on `xxx.py`.

```
print('hello world')
```

Intended use :

- x
- x
