# UlasKelas Backend

Final Project's Backend of Mobile Development SIG 2020 using Django Rest Framework.

## Getting Started

Follow the [General README](../README.md) first.

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

<!-- TODO: 
### Set up database from scratch
### Use populated database
 -->

### Run app

```bash
python manage.py runserver
# --- or ---
# press F5 on VS Code
```

Now you can login with superuser you just create on <https://localhost:8000> and interact with API view OR call the API endpoint with [cURL](https://curl.haxx.se/) or [Postman](https://www.postman.com/).
