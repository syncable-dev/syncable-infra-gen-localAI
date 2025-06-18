# prompt_templates.py

# This file contains the prompt templates for generating infrastructure artifacts.
# Separating them from the main logic makes the system cleaner and easier to maintain.
# These prompts are designed based on the key findings of the research report,
# incorporating system roles, policies, and few-shot (good vs. bad) examples.

# ==============================================================================
# DOCKERFILE GENERATION PROMPTS
# ==============================================================================

DOCKERFILE_SYSTEM_PROMPT = """
You are an expert DevSecOps Engineer specializing in creating secure, optimized, and production-ready Dockerfiles.
Your goal is to create Dockerfiles that strictly follow industry best practices.

**Core Policies:**
- **Security First:** Always use a non-root user. Minimize attack surface. Do not hardcode secrets.
- **Optimization:** Always use multi-stage builds to create minimal final images. This is non-negotiable.
- **Reproducibility:** Always use specific, version-locked base image tags provided in the prompt. NEVER use 'latest'.
- **Output Format:** Output ONLY the raw Dockerfile content. Do not add any other text, explanations, or markdown formatting.
"""

DOCKERFILE_USER_PROMPT = """
**Your Task:**
Generate a secure, multi-stage Dockerfile for the project described below.
Analyze the provided project files to determine the language, dependencies, build steps, and the correct run command.
Follow the best practices demonstrated in the GOOD examples. Avoid the mistakes shown in the BAD examples.

---
### CONTEXT: PROJECT FILES (Retrieved via RAG)

**1. Dependency Manifest (e.g., package.json, requirements.txt):**
```
{manifest_content}
```

**2. Main Entrypoint File Content:**
```
{entrypoint_content}
```

**3. Other Relevant Code Snippets:**
```
{other_relevant_snippets}
```
---
### EXAMPLES: GOOD vs. BAD Dockerfiles [Report Section 4]

#### Bad Python Example (What to AVOID):
```dockerfile
# BAD: Uses 'latest' tag, non-deterministic.
FROM python:latest
# BAD: Runs as root user, a major security risk.
WORKDIR /app
# BAD: Copies everything, including secrets or .git files. Poor caching.
COPY . .
# BAD: Can lead to a bloated image with development dependencies.
RUN pip install -r requirements.txt
EXPOSE 5000
# BAD: Simple run command, less robust for production.
CMD python app.py
```

#### Good Python Example (What to FOLLOW):
```dockerfile
# GOOD: Specific, version-locked, slim base image for the build stage.
FROM python:3.11-slim-buster AS builder
WORKDIR /app
# GOOD: Caches dependencies by copying the manifest first.
COPY requirements.txt .
# GOOD: Installs only production dependencies securely and cleans up cache.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# GOOD: Starts a new, clean, minimal stage for the final image.
FROM python:3.11-slim-buster AS final
WORKDIR /app
# GOOD: Creates a non-root user for enhanced security.
RUN useradd --create-home --shell /bin/bash appuser
# GOOD: Copies only necessary built code from the builder stage.
COPY --from=builder /app .
# GOOD: Sets permissions correctly for the non-root user.
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 5000
# GOOD: More robust entrypoint using exec form.
CMD ["python", "app.py"]
```

#### Bad TypeScript/Node.js Example (What to AVOID):
```dockerfile
# BAD: Uses 'latest' tag.
FROM node:latest
# BAD: Runs as root.
WORKDIR /usr/src/app
# BAD: Copies all files, invalidating cache on any file change.
COPY . .
# BAD: Runs full install including devDependencies in the final image.
RUN npm install
# BAD: Missing build step for TypeScript.
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

#### Good TypeScript/Node.js Example (What to FOLLOW):
```dockerfile
# syntax=docker/dockerfile:1.4
# GOOD: Version-locked, minimal base image for building.
FROM node:20-alpine AS builder
WORKDIR /usr/src/app
# GOOD: Copies only manifests to cache dependencies effectively.
COPY package*.json ./
# GOOD: Uses `npm ci` for fast, reliable, reproducible builds.
RUN npm ci
COPY . .
# GOOD: Explicit build step for TypeScript.
RUN npm run build

# GOOD: Minimal final stage from a clean base.
FROM node:20-alpine AS final
WORKDIR /usr/src/app
# GOOD: Creates a non-root user and group for security.
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
# GOOD: Copies only necessary production node_modules and built code from builder.
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/dist ./dist
EXPOSE 3000
# GOOD: Runs the built application using exec form.
CMD ["node", "dist/server.js"]
```
---
**Instructions:**
Generate the Dockerfile now for the project: '{project_name}'. Use the latest recommended base image tag for this language: `{latest_base_image_tag}`.
"""


# ==============================================================================
# DOCKER-COMPOSE GENERATION PROMPTS
# [Implements Report Sections 3, 4, 5, 6, 7]
# ==============================================================================

DOCKER_COMPOSE_SYSTEM_PROMPT = """
You are an expert Cloud Architect creating secure, production-ready Docker Compose configurations.

**Core Policies:**
- **Security:** NEVER hardcode secrets. Always reference an `.env` file (`env_file: .env`).
- **Persistence:** Always use named volumes for stateful services like databases. This is critical.
- **Isolation:** Always use a custom bridge network to connect services. Do not use the default bridge.
- **Reproducibility:** Always use specific, version-locked image tags for all services.
- **Output Format:** Output ONLY the raw `docker-compose.yml` content. Do not add any other text, explanations, or markdown formatting.
"""

DOCKER_COMPOSE_USER_PROMPT = """
**Your Task:**
Generate a `docker-compose.yml` file for the project described below.
Analyze the provided context to identify the main application and any required services (like a database or cache).
Follow the best practices from the GOOD example and avoid the mistakes from the BAD example.

---
### CONTEXT: PROJECT FILES (Retrieved via RAG)

**1. Dependency Manifest (e.g., package.json, requirements.txt):**
```
{manifest_content}
```

**2. Main Entrypoint File Content:**
```
{entrypoint_content}
```

**3. Other Relevant Code Snippets:**
```
{other_relevant_snippets}
```
---
### EXAMPLES: GOOD vs. BAD Docker Compose [Report Section 4]

#### Bad Example (What to AVOID):
```yaml
# BAD: Outdated version.
version: '2'
services:
  web:
    # BAD: relies on a pre-built image, not the local Dockerfile.
    image: my-app
    ports:
      - "5000:5000"
    # BAD: Hardcoded secrets, a massive security risk.
    environment:
      - DATABASE_URL=postgres://user:password@db:5432/mydb
  db:
    # BAD: Non-deterministic 'latest' tag.
    image: postgres:latest
    # BAD: Bind mount, not a named volume. Less manageable and portable.
    volumes:
      - ./postgres_data:/var/lib/postgresql/data
```

#### Good Example (What to FOLLOW):
```yaml
# GOOD: Modern, stable version.
version: '3.8'
services:
  app:
    # GOOD: Builds the application from the local Dockerfile.
    build: .
    container_name: {project_name}-app
    # GOOD: Uses an .env file for all environment variables, keeping secrets out of code.
    env_file: .env
    ports:
      - "5000:5000"
    # GOOD: Explicitly depends on the database service for startup order.
    depends_on:
      - db
    # GOOD: Connects to a custom network for secure isolation.
    networks:
      - app-net
  db:
    # GOOD: Specific, version-locked image provided in the prompt.
    image: postgres:{postgres_image_tag}
    container_name: {project_name}-db
    env_file: .env
    # GOOD: Uses a named volume for robust, managed data persistence.
    volumes:
      - db-data:/var/lib/postgresql/data
    networks:
      - app-net
    # GOOD: Basic healthcheck ensures the database is ready before the app starts.
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5

# GOOD: Defines the custom network for service isolation.
networks:
  app-net:
    driver: bridge

# GOOD: Defines the named volume for manageable persistence.
volumes:
  db-data:
```
---
**Instructions:**
Generate the `docker-compose.yml` for the project: '{project_name}'.
Infer the required services from the context. If 'redis' is detected, add a redis service. If 'postgres', 'psycopg2', or 'sqlalchemy' is detected, add the 'db' service as shown in the good example.
Use the image `postgres:{postgres_image_tag}` for the database and `redis:{redis_image_tag}` for the cache.
"""
