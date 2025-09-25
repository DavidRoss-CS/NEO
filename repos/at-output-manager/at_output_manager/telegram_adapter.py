"""
Telegram adapter for delivering trading notifications via bot API.
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import asyncio
from telegram import Bot, Update
from telegram.error import TelegramError
import structlog

from .notification_formatter import NotificationFormatter

logger = structlog.get_logger()

class TelegramAdapter:
    """Telegram bot adapter for trading notifications"""

    def __init__(self, bot_token: str, chat_id: str, formatter: NotificationFormatter):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.formatter = formatter
        self.bot = None
        self._initialized = False

    async def initialize(self):
        """Initialize Telegram adapter"""
        try:
            # Create Telegram bot instance
            self.bot = Bot(token=self.bot_token)

            # Test bot connectivity
            await self._test_bot()

            self._initialized = True
            logger.info(
                "Telegram adapter initialized",
                bot_username=await self._get_bot_username(),
                chat_id=self.chat_id
            )

        except Exception as e:
            logger.error(f"Failed to initialize Telegram adapter: {e}")
            raise

    async def _test_bot(self):
        """Test Telegram bot connectivity"""
        try:
            # Get bot info to test connectivity
            bot_info = await self.bot.get_me()

            # Send test message
            test_message = (
                "🤖 <b>NEO Trading System</b>\n\n"
                "✅ Telegram bot initialized successfully\n"
                f"🕐 <i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
            )

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=test_message,
                parse_mode='HTML'
            )

            logger.info(
                "Telegram bot test successful",
                bot_id=bot_info.id,
                bot_username=bot_info.username
            )

        except Exception as e:
            logger.warning(f"Telegram bot test failed: {e}")
            # Don't fail initialization for test failure

    async def _get_bot_username(self) -> str:
        """Get bot username for logging"""
        try:
            bot_info = await self.bot.get_me()
            return bot_info.username
        except Exception:
            return "unknown"

    async def send_notification(self, agent_output: Dict[str, Any], corr_id: str) -> str:
        """Send notification to Telegram"""
        if not self._initialized:
            raise RuntimeError("Telegram adapter not initialized")

        delivery_id = f"telegram_{uuid.uuid4().hex[:8]}"

        try:
            # Format message for Telegram
            telegram_message, reply_markup = await self.formatter.format_for_telegram(agent_output)

            # Send message to Telegram
            message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=telegram_message,
                parse_mode='HTML',
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )

            # Send orders as separate messages if they exist
            orders = agent_output.get('orders', [])
            if orders:
                await self._send_orders_details(orders, corr_id)

            logger.info(
                "Telegram notification sent successfully",
                corr_id=corr_id,
                delivery_id=delivery_id,
                message_id=message.message_id,
                agent_type=agent_output.get('agent_type'),
                confidence=agent_output.get('confidence'),
                orders_count=len(orders)
            )

            return delivery_id

        except TelegramError as e:
            logger.error(
                "Telegram API error",
                corr_id=corr_id,
                delivery_id=delivery_id,
                error=str(e),
                error_code=getattr(e, 'error_code', None)
            )
            raise

        except Exception as e:
            logger.error(
                "Telegram notification failed",
                corr_id=corr_id,
                delivery_id=delivery_id,
                error=str(e),
                agent_type=agent_output.get('agent_type')
            )
            raise

    async def _send_orders_details(self, orders: list, corr_id: str):
        """Send detailed order information as separate message"""
        try:
            if not orders:
                return

            orders_text = "📋 <b>Trading Orders Details:</b>\n\n"

            for i, order in enumerate(orders, 1):
                side_emoji = "📈" if order.get('side', '').lower() == 'buy' else "📉"
                orders_text += (
                    f"{side_emoji} <b>Order {i}:</b>\n"
                    f"   • <b>Symbol:</b> {order.get('symbol', 'N/A')}\n"
                    f"   • <b>Side:</b> {order.get('side', 'N/A').upper()}\n"
                    f"   • <b>Type:</b> {order.get('type', 'N/A').upper()}\n"
                    f"   • <b>Quantity:</b> {order.get('quantity', 'N/A')}\n"
                )

                if order.get('price'):
                    orders_text += f"   • <b>Price:</b> ${order['price']:,.2f}\n"

                if order.get('reasoning'):
                    orders_text += f"   • <b>Reason:</b> {order['reasoning']}\n"

                orders_text += "\n"

            # Split message if too long (Telegram limit is 4096 chars)
            if len(orders_text) > 4000:
                orders_text = orders_text[:4000] + "...\n\n<i>Message truncated</i>"

            await self.bot.send_message(
                chat_id=self.chat_id,
                text=orders_text,
                parse_mode='HTML'
            )

        except Exception as e:
            logger.warning(f"Failed to send orders details: {e}", corr_id=corr_id)

    async def send_custom_message(self, text: str, parse_mode: str = 'HTML') -> int:
        """Send custom message (for admin/debugging purposes)"""
        if not self._initialized:
            raise RuntimeError("Telegram adapter not initialized")

        try:
            message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode
            )
            return message.message_id

        except Exception as e:
            logger.error(f"Custom message send failed: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Check Telegram adapter health"""
        health_status = {
            "initialized": self._initialized,
            "bot_configured": bool(self.bot_token),
            "chat_configured": bool(self.chat_id)
        }

        if self._initialized and self.bot:
            try:
                # Test bot connectivity
                bot_info = await self.bot.get_me()
                health_status.update({
                    "bot_responsive": True,
                    "bot_username": bot_info.username,
                    "bot_id": bot_info.id
                })
            except Exception as e:
                health_status.update({
                    "bot_responsive": False,
                    "bot_error": str(e)
                })

        return health_status

    async def cleanup(self):
        """Clean up Telegram adapter resources"""
        if self.bot:
            # Close bot connection
            try:
                await self.bot.close()
            except Exception as e:
                logger.warning(f"Error closing Telegram bot: {e}")

        logger.info("Telegram adapter cleanup completed")