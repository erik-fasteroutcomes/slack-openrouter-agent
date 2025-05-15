# Slack OpenRouter Agent

This project is a Slack bot that uses OpenRouter to answer questions. It is built using FastAPI and Flask, and it integrates with Slack's API to handle events and respond to messages.

## Features

- Responds to Slack events, specifically `app_mention` events.
- Uses OpenRouter with the OpenAI GPT-4 model to generate responses to user prompts.
- Verifies Slack requests using signatures to ensure security.

## Requirements

- Python 3.11
- Poetry for dependency management

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd slack-openrouter-agent
   ```

2. **Install dependencies:**

   Use Poetry to install the required dependencies:

   ```bash
   poetry install
   ```

3. **Environment Variables:**

   Create a `.env` file in the root directory and add the following environment variables:

   ```plaintext
   SLACK_BOT_TOKEN=<your-slack-bot-token>
   SLACK_SIGNING_SECRET=<your-slack-signing-secret>
   SLACK_BOT_USER_ID=<your-slack-bot-user-id>
   OPENROUTER_API_KEY=<your-openrouter-api-key>
   ```

