# Poker Banker

Texas Hold'em Poker Banker Automation Management System.

## Quick Start

```bash
# Start PostgreSQL
docker compose up db -d

# Install dependencies
cd backend
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload

# Run tests
pytest
```
