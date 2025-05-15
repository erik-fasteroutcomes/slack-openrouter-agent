import os
import json
import asyncio
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from app.openrouter_client import query_openrouter
from app.slack_events import verify_slack_signature

load_dotenv()
app = FastAPI()
slack_client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))


@app.post("/slack/events")
async def slack_events(request: Request):
    raw_body = await request.body()
    verify_slack_signature(request, raw_body)

    payload = json.loads(raw_body)

    # Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    if payload["type"] == "event_callback":
        event = payload["event"]

        # Ignore all bot-generated messages
        if "bot_id" in event or event.get("user") == os.getenv("SLACK_BOT_USER_ID"):
            return {"ok": True}

        # Sanity check: ignore if user is missing
        if "user" not in event:
            return {"ok": True}

        if event["type"] == "app_mention":
            asyncio.create_task(handle_app_mention(event))
            return {"ok": True}

    return {"ok": True}


async def handle_app_mention(event: dict):
    text = event["text"]
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])

    prompt = text.split(maxsplit=1)[1] if " " in text else ""

    if not prompt:
        await slack_client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text="Please include a prompt after the mention."
        )
        return {"ok": True}

    reply = await query_openrouter(prompt)

    await slack_client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=reply
    )


# import os
# from fastapi import FastAPI, Request
# from dotenv import load_dotenv
# from slack_sdk.web.async_client import AsyncWebClient
# from app.openrouter_client import query_openrouter
# from app.slack_events import verify_slack_signature
# from urllib.parse import parse_qs
# load_dotenv()
# app = FastAPI()
# slack_client = AsyncWebClient(token=os.getenv("SLACK_BOT_TOKEN"))


# @app.post("/slack/events")
# async def slack_events(request: Request):
#     raw_body = await request.body()
#     verify_slack_signature(request, raw_body)

#     form_data = parse_qs(raw_body.decode())
#     text = form_data["text"][0]
#     channel_id = form_data["channel_id"][0]
#     thread_ts_list = form_data.get("thread_ts")

#     reply = await query_openrouter(text)
#     kwargs = dict(channel=channel_id, text=reply)
#     if thread_ts_list:
#         kwargs["thread_ts"] = thread_ts_list[0]

#     await slack_client.chat_postMessage(**kwargs)
#     return {"response_type": "ephemeral", "text": "Working on it..."}
