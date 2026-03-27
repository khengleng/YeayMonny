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
- User profile capture for outreach:
  - optional email, phone, Telegram username
  - explicit marketing opt-in flag + timestamp
  - operator CSV export for broadcast campaigns
- Multimodal input:
  - web users can upload voice and images
  - Telegram users can send voice and photos
  - app transcribes/analyzes and uses results in fortune reading context
  - face images now go through a rule-based face-reading engine
    (forehead, eyes, nose, mouth, chin, ears) before final reading
  - palm images now go through a rule-based palm-reading engine
    (heart line, head line, life line, fate line, sun line) before final reading
  - vehicle plate numerology helper:
    - extracts plate from user text
    - computes alphanumeric total + root number
    - adds Khmer guidance for driving/luck style
  - house-number numerology helper:
    - supports formats like `A59`, `14/18`, `47A`
    - follows moving-number calculation pattern
    - computes root number + Khmer meaning
  - compatibility engine:
    - estimates love compatibility score from user+partner birth cues
    - blends zodiac, life-path, and sign-group signals
    - adds stage-aware guidance (dating/married/breakup/reconnect intent)
  - financial advisory engine:
    - gives simple money-planning guidance from user context
    - includes risk level + practical action steps
- Built-in astrology context engine (local, no extra provider):
  - parses birth info
  - derives Chinese zodiac animal
  - derives Western sign when date is available
  - derives life-path number
  - derives WOFS-style Feng Shui cues:
    - Kua number (male/female)
    - favorable + caution directions
    - element colors
    - zodiac harmony/conflict hints
    - annual Flying Star center + sector highlights
    - Tai Sui and Sui Po yearly direction hints
  - applies Chinese zodiac relation rules inspired by TravelChinaGuide:
    - 4-year apart tendency (more harmonious)
    - 6-year opposite sign caution
    - 3-year apart tendency (more friction)
  - injects these into OpenAI prompt context before each reply
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
- `OPENAI_TRANSCRIBE_MODEL`
- `OPENAI_VISION_MODEL`
- `MAX_IMAGE_UPLOAD_MB`
- `MAX_AUDIO_UPLOAD_MB`
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
   - `OPENAI_TRANSCRIBE_MODEL=gpt-4o-mini-transcribe`
   - `OPENAI_VISION_MODEL=gpt-4.1-mini`
   - `MAX_IMAGE_UPLOAD_MB=8`
   - `MAX_AUDIO_UPLOAD_MB=15`
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
- `/webhooks/telegram/` Telegram webhook endpoint
- `/operator/login/` operator login page
- `/operator/` operator configuration portal (permission-based)

## Operator roles (Editor/Admin)

The operator portal now supports separate roles:

- `Prompt Editor`
  - can view operator portal
  - can edit only `system_prompt`
- `Prompt Admin`
  - can view operator portal
  - can edit `system_prompt`
  - can edit advanced settings (`model_name`, `temperature`)
  - can rollback to previous prompt/config versions

Quick setup (after migrate):

```bash
python manage.py setup_operator_roles
```

Assign users while creating roles:

```bash
python manage.py setup_operator_roles --editor-user <editor_username> --admin-user <admin_username>
```

Or assign users from Django Admin:

- `/admin/` -> `Authentication and Authorization` -> `Groups`
- add user to `Prompt Editor` or `Prompt Admin`

## Version history and rollback

- Every prompt/config update creates a snapshot in `AssistantConfigHistory`
- Rollback is available from `/operator/` for `Prompt Admin` only
- Full history is visible in `/admin/` as `Assistant Configuration History`

## Operations portal capabilities

The `/operator/` portal is not only for prompt editing. It now includes:

- Live operations metrics (total conversations, total messages, last 24h activity)
- Integration readiness status (OpenAI and Telegram)
- Conversation monitoring with search and pagination
- Recent message feed with links to full conversation transcript
- Dedicated conversation detail page for support review

## Telegram setup

1. Add environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_WEBHOOK_SECRET`
   - `TELEGRAM_WEBHOOK_PATH=/webhooks/telegram/`
2. Deploy app.
3. Register webhook:

```bash
TOKEN="<your-telegram-bot-token>"
BASE_URL="https://<your-railway-domain>"
SECRET="<your-telegram-webhook-secret>"

curl "https://api.telegram.org/bot${TOKEN}/setWebhook?url=${BASE_URL}/webhooks/telegram/&secret_token=${SECRET}"
curl "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```

## Run with Docker (local desktop)

1. Update `.env.docker` (add `OPENAI_API_KEY` if you want real AI replies).
2. Start services:

```bash
docker compose up --build -d
```

3. Open app:

- http://localhost:8000/

4. View logs:

```bash
docker compose logs -f web
```

5. Stop services:

```bash
docker compose down
```
