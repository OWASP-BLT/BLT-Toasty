# GitHub App Setup Guide

This guide will walk you through setting up a GitHub App for Toasty and testing it with a ping/pong command.

## Prerequisites

- A GitHub account
- Access to create GitHub Apps (organization owner or personal account)
- A server or local environment where Toasty is running
- A publicly accessible URL for webhooks (use ngrok for local testing)

## Step 1: Create a GitHub App

1. Navigate to GitHub Settings:
   - For personal account: Go to **Settings** > **Developer settings** > **GitHub Apps**
   - For organization: Go to **Organization Settings** > **Developer settings** > **GitHub Apps**

2. Click **New GitHub App**

3. Fill in the basic information:
   - **GitHub App name**: `Toasty-YourName` (must be unique across GitHub)
   - **Homepage URL**: Your repository URL or `https://github.com/OWASP-BLT/Toasty`
   - **Webhook URL**: `https://your-domain.com/aibot/webhook/` 
     - For local testing with ngrok: `https://your-ngrok-url.ngrok.io/aibot/webhook/`
   - **Webhook secret**: Generate a strong random string (save this for later)
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```

4. Set permissions (under "Repository permissions"):
   - **Issues**: Read & Write (for responding to issue comments)
   - **Pull requests**: Read & Write (for code review comments)
   - **Contents**: Read-only (for accessing code)
   - **Metadata**: Read-only (mandatory)

5. Subscribe to events (under "Subscribe to events"):
   - [x] Issue comment
   - [x] Issues
   - [x] Pull request
   - [x] Pull request review
   - [x] Pull request review comment

6. Set "Where can this GitHub App be installed?":
   - Choose **Only on this account** (for testing)

7. Click **Create GitHub App**

## Step 2: Generate and Download Private Key

1. After creating the app, scroll down to the **Private keys** section
2. Click **Generate a private key**
3. A `.pem` file will be downloaded - **keep this secure!**
4. Save it in a secure location (do NOT commit it to the repository)

## Step 3: Install the GitHub App

1. From your GitHub App settings page, click **Install App** in the left sidebar
2. Select the account/organization where you want to install it
3. Choose either:
   - **All repositories** (not recommended for testing)
   - **Only select repositories** (recommended) - select the repository you want to use for testing

4. Click **Install**

5. Note the **Installation ID** from the URL (e.g., `https://github.com/settings/installations/12345678`)

## Step 4: Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Add the following to your `.env` file:
   ```env
   SECRET_KEY=your-django-secret-key
   GEMINI_API_KEY=your-gemini-api-key
   
   # GitHub App Configuration
   GITHUB_APP_ID=your-app-id
   GITHUB_APP_PRIVATE_KEY_PATH=/path/to/your-private-key.pem
   GITHUB_WEBHOOK_SECRET=your-webhook-secret
   GITHUB_APP_INSTALLATION_ID=your-installation-id
   ```

   Where:
   - `GITHUB_APP_ID`: Found on your GitHub App settings page (e.g., `123456`)
   - `GITHUB_APP_PRIVATE_KEY_PATH`: Absolute path to the `.pem` file you downloaded
   - `GITHUB_WEBHOOK_SECRET`: The webhook secret you generated in Step 1
   - `GITHUB_APP_INSTALLATION_ID`: The installation ID from Step 3

   Alternatively, you can set the private key directly as a string:
   ```env
   GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
   ```

## Step 5: Set Up Local Development with ngrok (Optional)

If you're testing locally, you'll need to expose your local server to the internet:

1. Install ngrok: https://ngrok.com/download

2. Start your Django server:
   ```bash
   poetry run python manage.py runserver
   ```

3. In another terminal, start ngrok:
   ```bash
   ngrok http 8000
   ```

4. Copy the HTTPS forwarding URL (e.g., `https://abc123.ngrok.io`)

5. Update your GitHub App's webhook URL:
   - Go to your GitHub App settings
   - Update **Webhook URL** to: `https://abc123.ngrok.io/aibot/webhook/`
   - Click **Save changes**

## Step 6: Test the Setup with Ping/Pong

Now let's verify everything is working:

1. Make sure your server is running:
   ```bash
   poetry run python manage.py runserver
   ```

2. In any issue or pull request in your installed repository, create a comment:
   ```
   /ping
   ```

3. The bot should respond with:
   ```
   🏓 Pong! The GitHub App is working correctly.
   ```

## Troubleshooting

### Webhook not receiving events

1. Check your GitHub App's webhook delivery page:
   - Go to your GitHub App settings
   - Click **Advanced** tab
   - Check **Recent Deliveries**
   - Look for failed deliveries and error messages

2. Verify your webhook URL is publicly accessible:
   ```bash
   curl -I https://your-webhook-url.com/aibot/webhook/
   ```

3. Check your server logs for errors

### Authentication errors

1. Verify your `.pem` file is valid:
   ```bash
   openssl rsa -in your-private-key.pem -check
   ```

2. Ensure your `GITHUB_APP_ID` is correct (it's a number, not the app name)

3. Verify the webhook secret matches what you set in GitHub

### Bot not responding to commands

1. Check the server logs for errors
2. Verify the app has the correct permissions (Issues: Read & Write)
3. Make sure the app is installed on the correct repository
4. Try the ping command in a new comment (not editing an existing one)

## Security Best Practices

1. **Never commit your private key** - Add `*.pem` to `.gitignore`
2. **Use environment variables** - Don't hardcode secrets
3. **Rotate your webhook secret** periodically
4. **Use HTTPS only** for webhook URLs
5. **Validate webhook signatures** - The app does this automatically
6. **Limit permissions** - Only grant what's necessary
7. **Monitor webhook deliveries** - Check for suspicious activity

## Next Steps

Now that your GitHub App is set up and working:

1. Explore the code in `aibot/views.py` to understand how webhooks are handled
2. Add custom commands beyond `/ping`
3. Implement code review features using the AI models
4. Configure CI/CD for automatic deployment

## Resources

- [GitHub Apps Documentation](https://docs.github.com/en/developers/apps)
- [Webhook Events and Payloads](https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads)
- [Authenticating as a GitHub App](https://docs.github.com/en/developers/apps/building-github-apps/authenticating-with-github-apps)
