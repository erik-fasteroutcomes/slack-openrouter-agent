import hashlib
import hmac
import os
import time
from fastapi import Request, HTTPException


def verify_slack_signature(request: Request, body: bytes):
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    if abs(time.time() - int(timestamp)) > 60 * 5:
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    sig_basestring = f"v0:{timestamp}:{body.decode()}"
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
        raise HTTPException(status_code=400, detail="Invalid signature")
