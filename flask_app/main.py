import hashlib
import hmac
import os
from threading import Thread
import time
import json
from flask import Flask, request, jsonify
import httpx
from dotenv import load_dotenv
from slack_sdk.web.client import WebClient

load_dotenv()
app = Flask(__name__)
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

OPEN_ROUTER_LLM = "openai/gpt-4-turbo"
NUM_PREVIOUS_MESSAGES = 10
MAX_CHARS = 400_000

@app.route("/slack/events", methods=["POST"])
def slack_events():
    try:
        verify_result = verify_slack_signature()
        if verify_result is not None:
            return verify_result

        raw_body = request.data
        payload = json.loads(raw_body)

        if payload.get("type") == "url_verification":
            return jsonify({"challenge": payload["challenge"]})

        if payload["type"] == "event_callback":
            event = payload["event"]

            print(f"Received event: {event}")

            if "bot_id" in event or event.get("user") == os.getenv("SLACK_BOT_USER_ID"):
                return jsonify({"ok": True})

            if "user" not in event:
                return jsonify({"ok": True})

            if event["type"] == "app_mention":
                handle_app_mention_background(event)
                return jsonify({"ok": True})

            if event["type"] == "message" and event.get("channel_type") == "im":
                handle_dm_background(event)
                return jsonify({"ok": True})

        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error processing event: {e}")
        return jsonify({"ok": False}), 500


def handle_dm_background(event):
    def task():
        handle_dm(event)
    Thread(target=task).start()


def handle_app_mention_background(event):
    def task():
        handle_app_mention(event)
    Thread(target=task).start()


def handle_dm(event: dict):
    channel_id = event["channel"]
    root_ts = event.get("thread_ts", event["ts"])  # anchor to thread root

    messages = fetch_thread_history(channel_id, root_ts)
    if not messages:
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=root_ts,
            text="Please include a message."
        )
        return

    reply = query_openrouter(messages)

    slack_client.chat_postMessage(
        channel=channel_id,
        thread_ts=root_ts,
        text=reply
    )


def handle_app_mention(event: dict):
    channel_id = event["channel"]
    root_ts = event.get("thread_ts", event["ts"])  # anchor to thread root

    messages = fetch_thread_history(channel_id, root_ts)
    if not messages:
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=root_ts,
            text="Please include a prompt."
        )
        return

    reply = query_openrouter(messages)

    slack_client.chat_postMessage(
        channel=channel_id,
        thread_ts=root_ts,
        text=reply
    )

def fetch_thread_history(channel_id: str, thread_ts: str) -> list[dict]:
    try:
        response = slack_client.conversations_replies(channel=channel_id, ts=thread_ts)
        raw_messages = response.get("messages", [])
        messages = []

        total_chars = 0
        for msg in reversed(raw_messages):  # newest to oldest
            role = "assistant" if msg.get("user") == os.getenv("SLACK_BOT_USER_ID") else "user"
            content = msg.get("text", "")
            message_obj = {
                "role": role,
                "content": content
            }

            content_len = len(content)
            if total_chars + content_len > MAX_CHARS:
                break

            messages.insert(0, message_obj)  # keep chronological order
            total_chars += content_len

        return messages
    except Exception as e:
        print(f"Error fetching thread history: {e}")
        return []


def fetch_thread_history_last_num_messages(channel_id: str, thread_ts: str) -> list[dict]:
    try:
        response = slack_client.conversations_replies(channel=channel_id, ts=thread_ts)
        raw_messages = response.get("messages", [])
        last_num_messages = raw_messages[-NUM_PREVIOUS_MESSAGES:]

        formatted = []
        for msg in last_num_messages:
            role = "assistant" if msg.get("user") == os.getenv("SLACK_BOT_USER_ID") else "user"
            formatted.append({
                "role": role,
                "content": msg.get("text", "")
            })
        return formatted
    except Exception as e:
        print(f"Error fetching thread history: {e}")
        return []


def query_openrouter(messages: list[dict]) -> str:
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPEN_ROUTER_LLM,
        "messages": messages
    }
    with httpx.Client() as client:
        resp = client.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def verify_slack_signature():
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return jsonify({"error": "Invalid timestamp"}), 400

    sig_basestring = f"v0:{timestamp}:{request.data.decode()}"
    slack_signing_secret = os.getenv("SLACK_SIGNING_SECRET")

    if not slack_signing_secret:
        print("Missing signing secret")
        return jsonify({"error": "Missing signing secret"}), 500

    my_signature = (
        "v0="
        + hmac.new(
            slack_signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    slack_signature = request.headers.get("X-Slack-Signature", "")
    if not hmac.compare_digest(my_signature, slack_signature):
        return jsonify({"error": "Invalid signature"}), 400

    return None  # valid
