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

## API Endpoint

- **Sample Endpoint** : `GET /sample/`

You can call this to test if backend is working and API call succeed

```json
{
    "message": "API Call succeed on %Y-%m-%d %H:%M:%S"
}
```

- **Other Endpoint**: `GET /sample/`

Some description

Parameters:

```json
{
    "key": "value",
    "key": "value",
}
```

Return:

```json
{
    "key": "value",
    "key": "value",
}
```
