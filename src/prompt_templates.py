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
- **Output Format:** Output ONLY the raw Dockerfile content. Do not add any other text, explanations, markdown formatting, or code block wrappers. Do NOT include any #GOOD, #BAD, or example comments in the output. The output must be ready to build with `docker build`.
"""

DOCKERFILE_USER_PROMPT = """
**Your Task:**
Generate a secure, multi-stage Dockerfile for the project described below.
Analyze the provided project files to determine the language, dependencies, build steps, and the correct run command.
Use the provided file tree list (`tree_list`) to infer the correct build tool and dependency manager (e.g., poetry, pip, npm, yarn, etc.).
**IMPORTANT:**
- If `requirements.txt` is not present in the file tree, do NOT use it. If `pyproject.toml` or `poetry.lock` is present, use Poetry. If `Pipfile` is present, use pipenv. If `package.json` is present, use npm or yarn as appropriate. Always match the build process to the actual files in the tree.
- Output ONLY the raw Dockerfile content, with NO markdown code block wrappers, NO #GOOD/#BAD comments, and NO extra explanations. The output must be ready to build with `docker build`.

---
### CONTEXT: PROJECT FILES (Retrieved via RAG)

**1. Project Summary:**
{summary}

**2. File Tree:**
```
{tree}
```
**(File Tree List for Build Tool Inference):**
{tree_list}

**3. Dependency Manifest (e.g., package.json, requirements.txt):**
```
{manifest_content}
```

**4. Main Entrypoint File Content:**
```
{entrypoint_content}
```

**5. Other Relevant Code Snippets:**
```
{other_relevant_snippets}
```
---
### EXAMPLES: GOOD vs. BAD Dockerfiles [Report Section 4]

#### Bad Python Example (What to AVOID):
```dockerfile
FROM python:latest
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 5000
CMD python app.py
```

#### Good Python Example (What to FOLLOW):
```dockerfile
FROM python:3.11-slim-buster AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
FROM python:3.11-slim-buster AS final
WORKDIR /app
RUN useradd --create-home --shell /bin/bash appuser
COPY --from=builder /app .
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 5000
CMD ["python", "app.py"]
```

#### Bad TypeScript/Node.js Example (What to AVOID):
```dockerfile
FROM node:latest
WORKDIR /usr/src/app
COPY . .
RUN npm install
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

#### Good TypeScript/Node.js Example (What to FOLLOW):
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /usr/src/app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
FROM node:20-alpine AS final
WORKDIR /usr/src/app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/dist ./dist
EXPOSE 3000
CMD ["node", "dist/server.js"]
```
---
**Instructions:**
Generate the Dockerfile now for the project: '{project_name}'. Use the latest recommended base image tag for this language: `{latest_base_image_tag}`.
"""


# ==============================================================================
# DOCKER-COMPOSE GENERATION PROMPTS
# ==============================================================================

DOCKER_COMPOSE_SYSTEM_PROMPT = """
You are an expert Cloud Architect creating secure, production-ready Docker Compose configurations.

**Core Policies:**
- **Security:** NEVER hardcode secrets. Always reference an `.env` file (`env_file: .env`).
- **Persistence:** Always use named volumes for stateful services like databases. This is critical.
- **Isolation:** Always use a custom bridge network to connect services. Do not use the default bridge.
- **Reproducibility:** Always use specific, version-locked image tags for all services.
- **Output Format:** Output ONLY the raw `docker-compose.yml` content. Do not add any other text, explanations, markdown formatting, or code block wrappers. Do NOT include any #GOOD, #BAD, or example comments in the output. The output must be ready to use with `docker compose`.
"""

DOCKER_COMPOSE_USER_PROMPT = """
**Your Task:**
Generate a `docker-compose.yml` file for the project described below.
Analyze the provided context to identify the main application and any required services (like a database or cache).
Follow the best practices from the GOOD example and avoid the mistakes from the BAD example.

---
### CONTEXT: PROJECT FILES (Retrieved via RAG)

**1. Project Summary:**
{summary}

**2. File Tree:**
```
{tree}
```

**3. Dependency Manifest (e.g., package.json, requirements.txt):**
```
{manifest_content}
```

**4. Main Entrypoint File Content:**
```
{entrypoint_content}
```

**5. Other Relevant Code Snippets:**
```
{other_relevant_snippets}
```
---
### EXAMPLES: GOOD vs. BAD Docker Compose [Report Section 4]

#### Bad Example (What to AVOID):
```yaml
version: '2'
services:
  web:
    image: my-app
    ports:
      - "5000:5000"
    environment:
      - DATABASE_URL=postgres://user:password@db:5432/mydb
  db:
    image: postgres:latest
    volumes:
      - ./postgres_data:/var/lib/postgresql/data
```

#### Good Example (What to FOLLOW):
```yaml
version: '3.8'
services:
  app:
    build: .
    container_name: {project_name}-app
    env_file: .env
    ports:
      - "5000:5000"
    depends_on:
      - db
    networks:
      - app-net
  db:
    image: postgres:{postgres_image_tag}
    container_name: {project_name}-db
    env_file: .env
    volumes:
      - db-data:/var/lib/postgresql/data
    networks:
      - app-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${{POSTGRES_USER:-postgres}}"]
      interval: 10s
      timeout: 5s
      retries: 5
networks:
  app-net:
    driver: bridge
volumes:
  db-data:
```
---
**Instructions:**
Generate the `docker-compose.yml` for the project: '{project_name}'.
Infer the required services from the context. If 'redis' is detected, add a redis service. If 'postgres', 'psycopg2', or 'sqlalchemy' is detected, add the 'db' service as shown in the good example.
Use the image `postgres:{postgres_image_tag}` for the database and `redis:{redis_image_tag}` for the cache.
**IMPORTANT:**
- Output ONLY the raw docker-compose.yml content, with NO markdown code block wrappers, NO #GOOD/#BAD comments, and NO extra explanations. The output must be ready to use with `docker compose`.
"""
