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

### Install depedencies

```bash
pip install -r requirements.txt
```

#### Migrate database

```bash
python manage.py migrate
```

If this is the first time you migrate, you will see `db.sqlite3` after running command above.
But if you want to update the database

#### Update database

1. change or add the related models

2. make migrations file
```bash
python manage.py makemigrations
```

3. migrate database
```bash
python manage.py migrate
```
if after you migrate and the database not updated, please delete `db.sqlite3` file, and migrate again. 

<!-- TODO: 
will use postgresql later
 -->

#### Use populated database

```bash
python manage.py loaddata db.json
```

Rename `db_dump.sqlite3` to `db.sqlite3` if things not worked out and you're too lazy.

### Run app

```bash
python manage.py runserver
# --- or ---
# press F5 on VS Code
```

Now you can login with superuser you just create on <https://localhost:8000> and interact with API view OR call the API endpoint with [cURL](https://curl.haxx.se/) or [Postman](https://www.postman.com/).

## API Endpoint

Visit [/api/schema/swagger/](http://127.0.0.1:8000/api/schema/swagger/)

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
