"""
Slack adapter for delivering trading notifications via webhook.
"""

import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import httpx
import structlog

from .notification_formatter import NotificationFormatter

logger = structlog.get_logger()

class SlackAdapter:
    """Slack webhook adapter for trading notifications"""

    def __init__(self, webhook_url: str, formatter: NotificationFormatter):
        self.webhook_url = webhook_url
        self.formatter = formatter
        self.http_client = None
        self._initialized = False

    async def initialize(self):
        """Initialize Slack adapter"""
        try:
            # Create HTTP client with timeout and retries
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )

            # Test webhook connectivity
            await self._test_webhook()

            self._initialized = True
            logger.info("Slack adapter initialized", webhook_url_prefix=self.webhook_url[:50])

        except Exception as e:
            logger.error(f"Failed to initialize Slack adapter: {e}")
            raise

    async def _test_webhook(self):
        """Test Slack webhook connectivity"""
        try:
            test_payload = {
                "text": "🤖 NEO Trading System - Slack adapter initialized",
                "attachments": [
                    {
                        "color": "good",
                        "fields": [
                            {
                                "title": "Status",
                                "value": "Connection test successful",
                                "short": True
                            },
                            {
                                "title": "Timestamp",
                                "value": datetime.now(timezone.utc).isoformat(),
                                "short": True
                            }
                        ]
                    }
                ]
            }

            response = await self.http_client.post(
                self.webhook_url,
                json=test_payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:
                raise Exception(f"Webhook test failed: {response.status_code} - {response.text}")

            logger.info("Slack webhook test successful")

        except Exception as e:
            logger.warning(f"Slack webhook test failed: {e}")
            # Don't fail initialization for test failure - might be rate limited

    async def send_notification(self, agent_output: Dict[str, Any], corr_id: str) -> str:
        """Send notification to Slack"""
        if not self._initialized:
            raise RuntimeError("Slack adapter not initialized")

        delivery_id = f"slack_{uuid.uuid4().hex[:8]}"

        try:
            # Format message for Slack
            slack_message = await self.formatter.format_for_slack(agent_output)

            # Send to Slack
            response = await self.http_client.post(
                self.webhook_url,
                json=slack_message,
                headers={
                    "Content-Type": "application/json",
                    "X-Correlation-ID": corr_id,
                    "X-Delivery-ID": delivery_id
                }
            )

            # Check response
            if response.status_code != 200:
                raise Exception(f"Slack API error: {response.status_code} - {response.text}")

            logger.info(
                "Slack notification sent successfully",
                corr_id=corr_id,
                delivery_id=delivery_id,
                agent_type=agent_output.get('agent_type'),
                confidence=agent_output.get('confidence')
            )

            return delivery_id

        except Exception as e:
            logger.error(
                "Slack notification failed",
                corr_id=corr_id,
                delivery_id=delivery_id,
                error=str(e),
                agent_type=agent_output.get('agent_type')
            )
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Check Slack adapter health"""
        return {
            "initialized": self._initialized,
            "webhook_configured": bool(self.webhook_url),
            "http_client_ready": self.http_client is not None
        }

    async def cleanup(self):
        """Clean up Slack adapter resources"""
        if self.http_client:
            await self.http_client.aclose()

        logger.info("Slack adapter cleanup completed")