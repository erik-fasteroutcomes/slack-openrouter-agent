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


@app.route("/slack/events", methods=["POST"])
def slack_events():
    verify_result = verify_slack_signature()
    if verify_result is not None:
        return verify_result

    raw_body = request.data
    payload = json.loads(raw_body)

    # Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return jsonify({"challenge": payload["challenge"]})

    if payload["type"] == "event_callback":
        event = payload["event"]

        # Ignore bot messages
        if "bot_id" in event or event.get("user") == os.getenv("SLACK_BOT_USER_ID"):
            return jsonify({"ok": True})

        if "user" not in event:
            return jsonify({"ok": True})

        if event["type"] == "app_mention":
            handle_app_mention_background(event)
            return jsonify({"ok": True})

    return jsonify({"ok": True})

def handle_app_mention_background(event):
    def task():
        handle_app_mention(event)
    Thread(target=task).start()

def handle_app_mention(event: dict):
    text = event["text"]
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])

    prompt = text.split(maxsplit=1)[1] if " " in text else ""

    if not prompt:
        slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="Please include a prompt after the mention."
        )
        return

    reply = query_openrouter(prompt)

    slack_client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=reply
    )


def query_openrouter(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-4",
        "messages": [{"role": "user", "content": prompt}]
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
    my_signature = (
        "v0="
        + hmac.new(
            os.getenv("SLACK_SIGNING_SECRET").encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    slack_signature = request.headers.get("X-Slack-Signature", "")
    if not hmac.compare_digest(my_signature, slack_signature):
        return jsonify({"error": "Invalid signature"}), 400

    return None  # valid
