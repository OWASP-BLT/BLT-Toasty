# Toasty 🍞

The smart, context-aware AI code reviewer from OWASP BLT.

## Overview

Toasty is an AI-powered code review service designed to help developers improve code quality through automated analysis and intelligent suggestions. It consists of:

- **Django Application** (`/aibot`, `/toasty`) - Main Django-based application
- **Cloudflare Worker** (root directory) - Serverless Python backend using Cloudflare Workers
- **GitHub App** (`app.js`) - Responds to `/plan` and other slash commands on issues

## Features

- 🤖 **AI Code Reviews** - Automated, security-focused analysis of pull requests
- 📋 **/plan Command** - Comment `/plan` on any issue to receive a structured implementation plan
- 🚀 **Serverless Architecture** - Built on Cloudflare Workers for global low-latency
- 🔐 **Security-First** - HMAC signature validation, OWASP Top 10 detection

## Using the /plan Command

Once Toasty is installed on a repository, comment `/plan` on any issue to receive a structured code implementation plan:

1. Open or create an issue
2. Comment: `/plan`
3. Toasty responds with a detailed 6-step plan based on the issue title and description

## Project Structure

```
toasty/
├── app.js              # GitHub App webhook handler (/plan command)
├── app.yml             # GitHub App configuration
├── worker.py           # Cloudflare Worker backend
├── wrangler.toml       # Cloudflare Workers configuration
├── test_worker.py      # Worker tests
├── aibot/              # Django app for AI bot functionality
├── toasty/             # Django project settings
└── docs/               # GitHub Pages documentation
```

## Components

### GitHub App (Slash Commands)

The GitHub App listens for issue comments and responds to slash commands like `/plan`.

**Setup:**
```bash
# Install Node dependencies
npm install

# Start the GitHub App locally
npm start
```

Configure environment variables (copy `.env.example` to `.env`):
- `APP_ID` - Your GitHub App ID
- `WEBHOOK_SECRET` - Your webhook secret
- `PRIVATE_KEY_PATH` - Path to your private key

### Django Application

The main Django application provides the core functionality for Toasty.

**Setup:**
```bash
# Install dependencies
poetry install

# Run migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

### Cloudflare Worker Backend

A serverless backend built with Cloudflare Workers and Python for globally distributed, low-latency API endpoints.

**Features:**
- Health monitoring endpoints
- Code review API
- Status monitoring
- CORS support with preflight handling
- Comprehensive error handling and validation

**Quick Start:**
```bash
# Install Node dependencies (including Wrangler CLI)
npm install

# Run locally
npm run dev

# Deploy
npm run deploy
```

## API Endpoints

The Cloudflare Worker provides these REST endpoints:

- `GET /` - Service information
- `GET /health` - Health check
- `POST /api/review` - Submit code for review
- `GET /api/status` - Service status

See `worker.py` for detailed API documentation.

## Development

### Prerequisites

- Python >=3.13,<4.0.0
- Poetry (for Django app)
- Node.js 18+ and npm (for Cloudflare Worker and GitHub App)

### Installation

1. Clone the repository
2. Install Django dependencies: `poetry install`
3. Install Worker/App dependencies: `npm install`
4. Copy `.env.example` to `.env` and fill in your values

## Architecture

### Core Flow

1. GitHub sends webhook → Cloudflare Worker
2. Worker validates signature
3. Worker fetches PR data from GitHub API
4. Worker sends structured context to AI agent
5. Worker posts AI review back to GitHub

For the `/plan` command:
1. User comments `/plan` on an issue
2. GitHub App receives webhook
3. App generates structured implementation plan
4. App posts plan as a comment

## License

GNU Affero General Public License v3 - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) and ensure all changes are tested before submitting.
