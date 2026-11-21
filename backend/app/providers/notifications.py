"""
Outage notification provider interface and implementations.

Implements:
- NotificationProvider: Abstract base class for outage alert delivery.
- UnavailableNotificationProvider: Honest default raising NotificationProviderUnavailableError (HTTP 503).
- ConsoleNotificationProvider: Demo and testing provider logging messages and recording them in memory.
- TwilioNotificationProvider: Twilio SMS and WhatsApp provider (enabled when TWILIO_* credentials exist).
"""
from __future__ import annotations

import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class NotificationProviderUnavailableError(RuntimeError):
    """Raised when the configured notification provider is unreachable, misconfigured, or unavailable."""
    pass


class NotificationDeliveryError(RuntimeError):
    """Raised when an active notification provider fails to deliver a message."""
    pass


class NotificationProvider(ABC):
    """Abstract base class for incident notification delivery."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'unavailable', 'console', 'twilio')."""
        ...

    @abstractmethod
    def send_notification(
        self,
        recipient: str,
        message: str,
        channel: str = "sms",
        subscriber_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an outage alert to a subscriber via the designated channel.

        Args:
            recipient: Destination phone number or endpoint (e.g. '+919876543210').
            message: Grounded natural-language alert in subscriber's preferred language.
            channel: Target channel: 'sms' or 'whatsapp'.
            subscriber_id: Optional subscriber identifier.

        Returns:
            Dictionary containing message_id, status, recipient, channel, and provider.

        Raises:
            NotificationProviderUnavailableError: If provider is offline or misconfigured.
            NotificationDeliveryError: If message transmission fails.
        """
        ...


class UnavailableNotificationProvider(NotificationProvider):
    """
    Default honest fallback provider when no live notification service is configured.
    Refuses to fabricate delivery and raises NotificationProviderUnavailableError.
    """

    @property
    def provider_name(self) -> str:
        return "unavailable"

    def send_notification(
        self,
        recipient: str,
        message: str,
        channel: str = "sms",
        subscriber_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        raise NotificationProviderUnavailableError(
            "Outage notification provider is not configured. "
            "Set NOTIFICATION_PROVIDER=console for local demos or "
            "provide TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER for live delivery."
        )


class ConsoleNotificationProvider(NotificationProvider):
    """
    Console / In-Memory notification provider for local demos and testing.
    Logs messages and records sent items for verification.
    """

    def __init__(self) -> None:
        self.sent_messages: List[Dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return "console"

    def send_notification(
        self,
        recipient: str,
        message: str,
        channel: str = "sms",
        subscriber_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        msg_id = f"console-{uuid4().hex[:8]}"
        record = {
            "message_id": msg_id,
            "status": "sent",
            "recipient": recipient,
            "channel": channel.lower(),
            "subscriber_id": subscriber_id,
            "message": message,
            "provider": "console",
        }
        self.sent_messages.append(record)
        logger.info(
            "[CONSOLE OUTAGE NOTIFICATION] Channel: %s | To: %s | Sub: %s | ID: %s | Message: %s",
            channel.upper(),
            recipient,
            subscriber_id or "—",
            msg_id,
            message,
        )
        return record


class TwilioNotificationProvider(NotificationProvider):
    """
    Twilio notification provider supporting SMS and WhatsApp dispatch via Twilio REST API.
    Enabled only when TWILIO_* credentials are valid and non-blank.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        whatsapp_from_number: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if not account_sid or not account_sid.strip():
            raise NotificationProviderUnavailableError(
                "Twilio account SID is missing. Set TWILIO_ACCOUNT_SID."
            )
        if not auth_token or not auth_token.strip():
            raise NotificationProviderUnavailableError(
                "Twilio auth token is missing. Set TWILIO_AUTH_TOKEN."
            )
        if not from_number or not from_number.strip():
            raise NotificationProviderUnavailableError(
                "Twilio from number is missing. Set TWILIO_FROM_NUMBER."
            )

        self.account_sid = account_sid.strip()
        self.auth_token = auth_token.strip()
        self.from_number = from_number.strip()
        self.whatsapp_from_number = (whatsapp_from_number or from_number).strip()
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "twilio"

    def send_notification(
        self,
        recipient: str,
        message: str,
        channel: str = "sms",
        subscriber_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        channel_lower = channel.lower().strip()
        if channel_lower == "whatsapp":
            from_target = self.whatsapp_from_number
            if not from_target.startswith("whatsapp:"):
                from_target = f"whatsapp:{from_target}"
            to_target = recipient.strip()
            if not to_target.startswith("whatsapp:"):
                to_target = f"whatsapp:{to_target}"
        else:
            from_target = self.from_number
            to_target = recipient.strip()

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        form_data = urllib.parse.urlencode({
            "From": from_target,
            "To": to_target,
            "Body": message,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=form_data, method="POST")
        auth_str = f"{self.account_sid}:{self.auth_token}"
        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {b64_auth}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_bytes = resp.read()
                data = json.loads(resp_bytes.decode("utf-8"))
                sid = data.get("sid", f"twilio-{uuid4().hex[:8]}")
                msg_status = data.get("status", "sent")
                return {
                    "message_id": sid,
                    "status": msg_status,
                    "recipient": recipient,
                    "channel": channel_lower,
                    "subscriber_id": subscriber_id,
                    "provider": "twilio",
                }
        except urllib.error.HTTPError as exc:
            raw_err = exc.read().decode("utf-8", errors="replace")
            raise NotificationDeliveryError(
                f"Twilio API error HTTP {exc.code}: {raw_err}"
            ) from exc
        except Exception as exc:
            raise NotificationDeliveryError(
                f"Twilio transmission failure: {exc}"
            ) from exc
