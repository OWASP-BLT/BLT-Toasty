# Contributing to Toasty

Thank you for your interest in contributing to Toasty, the AI-powered code review assistant from OWASP BLT! This guide will help you get your development environment set up and walk you through the contribution process.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running the Django Application](#running-the-django-application)
- [Running the Cloudflare Worker](#running-the-cloudflare-worker)
- [Code Style and Linting](#code-style-and-linting)
- [Running Tests](#running-tests)
- [Submitting a Pull Request](#submitting-a-pull-request)

---

## Prerequisites

Before you begin, make sure you have the following installed:

- **Python** >= 3.13
- **Poetry** — dependency management for the Django app ([installation guide](https://python-poetry.org/docs/#installation))
- **Node.js** and **npm** — required for the Cloudflare Worker tooling
- **Docker** and **Docker Compose** — for running services (PostgreSQL, Redis, Qdrant) locally
- **Git**

---

## Getting Started

1. **Fork and clone the repository:**

   ```bash
   git clone https://github.com/<your-username>/BLT-Toasty.git
   cd BLT-Toasty
   ```

2. **Set up your environment variables:**

   ```bash
   cp .env.example .env
   ```

   Open `.env` and fill in the required values. See [Environment Variables](#environment-variables) for details.

3. **Install Django app dependencies:**

   ```bash
   poetry install
   ```

4. **Install Cloudflare Worker dependencies:**

   ```bash
   npm install
   ```

5. **Set up pre-commit hooks:**

   ```bash
   pip install pre-commit
   pre-commit install
   ```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Variable            | Description                                      | Required |
|---------------------|--------------------------------------------------|----------|
| `SECRET_KEY`        | Django secret key — run `python -c "import secrets; print(secrets.token_hex(50))"` to generate one | Yes      |
| `GEMINI_API_KEY`    | Google Gemini API key for AI features            | Yes      |
| `POSTGRES_USER`     | PostgreSQL username                              | Yes      |
| `POSTGRES_DB`       | PostgreSQL database name                         | Yes      |
| `POSTGRES_PASSWORD` | PostgreSQL password                              | Yes      |
| `POSTGRES_PORT`     | PostgreSQL port (default: `5432`)                | No       |
| `PORT`              | Application port (default: `8000`)               | No       |

> **Never commit your `.env` file.** It is already listed in `.gitignore`.

---

## Running the Django Application

### Option A: Using Docker Compose (Recommended)

Docker Compose starts all required services (PostgreSQL, Redis, Qdrant) along with the Django app and Celery worker.

```bash
docker compose up --build
```

The app will be available at [http://localhost:8000](http://localhost:8000).

To run only the backing services (so you can run Django locally):

```bash
docker compose up db redis qdrant
```

### Option B: Running Locally

Ensure your backing services (PostgreSQL, Redis, Qdrant) are running, then:

```bash
# Apply database migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

The app will be available at [http://localhost:8000](http://localhost:8000).

---

## Running the Cloudflare Worker

The Cloudflare Worker is a serverless Python backend deployed to Cloudflare's global edge network.

### Local Development

```bash
# Start the local dev server (available at http://localhost:8787)
npm run dev
```

### Deployment

```bash
# Deploy to Cloudflare Workers
npm run deploy
```

See [WORKER.md](WORKER.md) for full documentation on the worker, its API endpoints, and configuration.

---

## Code Style and Linting

This project uses several tools to enforce code quality. They are configured as pre-commit hooks and will run automatically before each commit.

| Tool      | Purpose                              | Config              |
|-----------|--------------------------------------|---------------------|
| `black`   | Python code formatting               | `pyproject.toml`    |
| `ruff`    | Python linting and import sorting    | `pyproject.toml`    |
| `bandit`  | Python security checks               | `pyproject.toml`    |
| `djlint`  | Django template formatting and linting | `pyproject.toml`  |

To run all checks manually:

```bash
pre-commit run --all-files
```

To run individual tools:

```bash
# Format code
black .

# Lint code
ruff check .

# Security scan
bandit -c pyproject.toml -r .
```

---

## Running Tests

### Django Application Tests

```bash
python manage.py test
```

### Cloudflare Worker Tests

```bash
python -m pytest test_worker.py
```

---

## Submitting a Pull Request

1. Create a new branch from `main`:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes, following the code style guidelines above.

3. Ensure all tests pass and linting is clean:

   ```bash
   pre-commit run --all-files
   python manage.py test
   python -m pytest test_worker.py
   ```

4. Commit your changes with a clear, descriptive message.

5. Push your branch and open a pull request against `main`.

6. Describe what your PR does and link any related issues.

---

## Questions or Issues?

If you have questions or run into problems, please [open an issue](https://github.com/OWASP-BLT/BLT-Toasty/issues) on GitHub.

Thank you for contributing! 🎉
