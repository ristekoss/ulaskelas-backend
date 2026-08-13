# UlasKelas Backend

Final Project's Backend of Mobile Development SIG 2021 using Django Rest Framework.



## Database Schmea

Database schema to as a guidance to data that will be used in this project

![image](https://user-images.githubusercontent.com/41831375/140859530-1576ebcf-9a2b-47ce-8f9d-c593195f2eff.png)

## Getting Started

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

1. duplicate ./UlasKelas/.env.sample and rename to .env

2. run postgres db
```bash
docker-compose up -d
```

3. activate env and install requirement
```bash
source env/bin/activate
pip install -r requirements.txt
```

4. run project
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

### Create or update database dev

before migrate db, make sure ulas-pg container running

1. change or add the related models

2. make migrations file && migrate database
```bash
python manage.py makemigrations
python manage.py migrate
```

### Create or update database prod

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

### Access db

```bash
docker exec -it ulas-pg bash
psql -U postgres
```

or use database management and input credentials provided in settings.py

Now you can login with superuser you just create on <https://localhost:8000> and interact with API view OR call the API endpoint with [cURL](https://curl.haxx.se/) or [Postman](https://www.postman.com/).

### Sunjad Endpoint Used

Sunjad all courses mock servers
https://3e081de5-8b4c-46ea-8736-99476c47204b.mock.pstmn.io/courses 

### Synchronize the cross-faculty course catalog

After applying migrations, populate all supported S1, D3, and D4 programs:

```bash
python manage.py migrate
python manage.py sync_courses --all
```

To refresh only one SSO/SunJad organization code:

```bash
python manage.py sync_courses --org-code 01.00.12.01
```

Configure the production managed scheduler to run the all-program command
daily at **02:00 Asia/Jakarta** (`0 2 * * *` when the scheduler supports an
explicit timezone, or `0 19 * * *` in UTC):

```bash
python manage.py sync_courses --all
```

Run the same command once immediately after the first deployment so the
catalog is populated without waiting for the next schedule. The scheduler
must retain stdout/stderr and alert on a non-zero exit status. A failed program
is reported at the end without preventing the remaining programs from being
synchronized. Programs that have no SunJad catalog yet are reported as
unavailable without changing their existing course statuses.

SunJad requests use a 5-second connection timeout, a 20-second read timeout,
and up to three attempts with exponential backoff for transient failures.
Course mappings are deactivated only after a valid catalog snapshot; failed or
untrusted responses never cause mass deactivation. Inactive courses stay in
the database so existing reviews and calculator history remain accessible.

Before the first sync after deploying course-code validation, audit invalid
legacy courses with the dry-run cleanup command:

```bash
python manage.py cleanup_invalid_course_codes
```

After reviewing the output and taking a database backup, apply the cleanup:

```bash
python manage.py cleanup_invalid_course_codes --apply
```

The cleanup deactivates invalid catalog mappings. Invalid courses are deleted
only when they have no review, bookmark, calculator, course-semester, or
TanyaTeman references; referenced courses are retained for manual remediation.

### Import the latest SLCM IRS period locally

This proof of concept runs only as a local management command. Install the
temporary browser used by Playwright:

```bash
pip install -r requirements-slcm.txt
python -m playwright install chromium
```

Run a preview for a local Teman Kuliah profile and calculator semester:

```bash
python manage.py import_slcm_irs \
    --username example.username \
    --semester 1 \
    --irs-url "https://slcm.ui.ac.id/path-to-irs" \
    --dry-run
```

The command opens an isolated browser at the supplied SLCM IRS page. Complete
the SLCM login; no terminal confirmation is needed. After authentication, the
command previews only the latest academic period that contains courses. Remove
`--dry-run` to confirm the database import in the same browser session.
Existing calculator courses are skipped, and SLCM codes missing from the local
catalog are reported. The command does not save SLCM credentials, cookies, page
HTML, or browser storage. Use `--login-timeout` to override the default
five-minute login window.


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
