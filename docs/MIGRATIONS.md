# Database Migrations Guide

This guide explains how to use Alembic for database migrations in this project.

## Quick Start

### First Time Setup

The database is automatically initialized on first run. For production, use migrations:

```bash
# Create initial migration (if not already done)
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

## Common Commands

### Create a Migration

**Auto-generate from model changes:**
```bash
alembic revision --autogenerate -m "Add user avatar field"
```

**Create empty migration (for manual SQL):**
```bash
alembic revision -m "Custom migration"
```

### Apply Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Apply up to a specific revision
alembic upgrade <revision_id>

# Apply one migration forward
alembic upgrade +1
```

### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to a specific revision
alembic downgrade <revision_id>

# Rollback all migrations
alembic downgrade base
```

### View Migration Status

```bash
# Show current revision
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic heads
```

## Workflow Example

### Adding a New Field to User Model

1. **Edit `models.py`:**
   ```python
   class User(Base):
       # ... existing fields ...
       avatar_url = Column(String(200), nullable=True)  # New field
   ```

2. **Generate migration:**
   ```bash
   alembic revision --autogenerate -m "Add avatar_url to users"
   ```

3. **Review the generated migration** in `alembic/versions/XXXX_add_avatar_url_to_users.py`

4. **Apply the migration:**
   ```bash
   alembic upgrade head
   ```

### Creating a New Model

1. **Add model to `models.py`:**
   ```python
   class Comment(Base):
       __tablename__ = "comments"
       
       id = Column(Integer, primary_key=True, index=True)
       content = Column(Text, nullable=False)
       post_id = Column(Integer, nullable=False)
       created_at = Column(DateTime(timezone=True), server_default=func.now())
   ```

2. **Import the model in `alembic/env.py`:**
   ```python
   from models import User, Post, Comment  # Add Comment
   ```

3. **Generate and apply migration:**
   ```bash
   alembic revision --autogenerate -m "Add comments table"
   alembic upgrade head
   ```

## Migration File Structure

Each migration file contains:

```python
"""Add avatar_url to users

Revision ID: abc123
Revises: def456
Create Date: 2024-01-01 12:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = 'def456'

def upgrade():
    # Changes to apply
    op.add_column('users', sa.Column('avatar_url', sa.String(200), nullable=True))

def downgrade():
    # Changes to rollback
    op.drop_column('users', 'avatar_url')
```

## Best Practices

1. **Always review auto-generated migrations** before applying them
2. **Test migrations** on a development database first
3. **Keep migrations small and focused** - one logical change per migration
4. **Never edit existing migrations** that have been applied to production
5. **Use descriptive migration messages** that explain what changed
6. **Test both upgrade and downgrade** paths

## Troubleshooting

### Migration conflicts

If you have conflicts between branches:

```bash
# Merge heads
alembic merge -m "Merge migration branches" <revision1> <revision2>
alembic upgrade head
```

### Database out of sync

If your database schema doesn't match your models:

```bash
# Check current state
alembic current

# Stamp to a specific revision (without running migrations)
alembic stamp head
```

### Reset database (Development only!)

⚠️ **Warning**: This deletes all data!

```bash
# Delete database file
rm app.db

# Recreate from migrations
alembic upgrade head
```

## Production Considerations

1. **Backup your database** before running migrations
2. **Test migrations** on a staging environment first
3. **Run migrations during maintenance windows** for large changes
4. **Monitor migration execution time** for performance impact
5. **Have a rollback plan** ready before applying migrations

