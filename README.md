# Python-Flask
Overview
Scenario. You are the DevOps engineer at a small logistics company. The warehouse team keeps stock levels in spreadsheets and wants a small JSON API that other services can call. A developer wrote a single-file prototype. Your job is to turn it into an application that can be deployed, tested and operated. That means:

a structured Flask application with an application factory, blueprints and environment-based configuration
persistence with Flask-SQLAlchemy (SQLite) and custom flask CLI commands for database tasks
consistent JSON error handling, input validation, request IDs, structured logging and health endpoints
an automated pytest suite with a coverage gate
a production WSGI server (Gunicorn) with signal-based reloads
a hardened, non-root Docker image with a health check
a Docker Compose stack with an Nginx reverse proxy, persistent storage and horizontal scaling
You will diagnose and fix realistic faults along the way: a missing secret, an unreachable database, a broken reverse proxy and a code regression.

What you will build

            curl (port 8080)
                  |
          +---------------+
          |  nginx proxy  |   X-Request-ID, X-Forwarded-For
          +---------------+
                  |
          +---------------+      +-------------------------+
          | gunicorn      |----->| SQLite on named volume  |
          | Flask app x N |      | /data/inventory.db      |
          +---------------+      +-------------------------+
