# Yeay Monny (យាយមុន្នី)

Production-ready Django chat app for a Khmer fortune teller persona.

## Stack

- Django 6
- OpenAI API
- PostgreSQL (production via `DATABASE_URL`)
- Django Admin
- Railway-ready deployment

## Features

- Khmer-first chat UI (mobile friendly)
- Fortune teller persona: **Yeay Monny / យាយមុន្នី**
- Uses the exact Khmer system prompt from `prompt.md`
- Chat history persisted in database
- Session-based conversation tracking
- Admin panel to inspect conversations/messages
- Safe guidance style (non-diagnostic, non-guaranteed outcomes)

## Local setup

1. Create and activate virtual env
2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Configure environment

```bash
cp .env.example .env
```

4. Run migrations

```bash
python manage.py migrate
```

5. Create admin user

```bash
python manage.py createsuperuser
```

6. Start app

```bash
python manage.py runserver
```

## Environment variables

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TIME_ZONE`

## Railway deployment

1. Push this repo to GitHub.
2. Create a Railway project from the repo.
3. Add PostgreSQL in Railway.
4. Set env vars:
   - `SECRET_KEY`
   - `DEBUG=False`
   - `ALLOWED_HOSTS=<your-domain>.up.railway.app`
   - `CSRF_TRUSTED_ORIGINS=https://<your-domain>.up.railway.app`
   - `OPENAI_API_KEY=<your-key>`
   - `DATABASE_URL` (usually auto-provided by Railway Postgres)
5. Deploy.
6. Run migrations in Railway shell:

```bash
python manage.py migrate
```

7. Create admin user in Railway shell:

```bash
python manage.py createsuperuser
```

## App routes

- `/` chat interface
- `/admin/` Django admin
