FROM python:3.11-alpine

# Install system dependencies, Python packages, and create non-root user in a single layer
RUN apk add --no-cache postgresql-client \
    && pip install --no-cache-dir alembic psycopg2-binary python-dotenv \
    && addgroup -S alembic \
    && adduser -S alembic -G alembic

# Set working directory
WORKDIR /app

# Copy Alembic configuration and migrations
COPY alembic.ini /app/
COPY migrations/postgresql /app/migrations/postgresql

# Change ownership of the app directory to the non-root user
RUN chown -R alembic:alembic /app

# Switch to non-root user
USER alembic

# Run migrations on container start
CMD ["alembic", "upgrade", "head"]
