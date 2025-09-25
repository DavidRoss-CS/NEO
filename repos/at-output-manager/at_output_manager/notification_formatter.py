"""
Notification formatter for converting agent outputs into channel-specific messages.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = structlog.get_logger()

class NotificationFormatter:
    """Formats agent outputs for different notification channels"""

    def __init__(self):
        self.confidence_thresholds = {
            'high': 0.8,
            'medium': 0.6,
            'low': 0.0
        }

    async def format_for_slack(self, agent_output: Dict[str, Any]) -> Dict[str, Any]:
        """Format agent output for Slack webhook"""
        try:
            # Extract key information
            agent_type = agent_output.get('agent_type', 'Unknown Agent')
            confidence = agent_output.get('confidence', 0.0)
            analysis = agent_output.get('analysis', 'No analysis provided')
            reasoning = agent_output.get('reasoning', 'No reasoning provided')
            orders = agent_output.get('orders', [])

            # Determine message color based on confidence
            color = self._get_confidence_color(confidence)

            # Create main message
            main_text = f"🤖 *{self._format_agent_name(agent_type)}* Analysis"

            # Create attachment with structured data
            attachment = {
                "color": color,
                "fields": [
                    {
                        "title": "📊 Analysis",
                        "value": self._truncate_text(analysis, 300),
                        "short": False
                    },
                    {
                        "title": "💪 Confidence",
                        "value": f"{confidence:.1%} {self._get_confidence_emoji(confidence)}",
                        "short": True
                    },
                    {
                        "title": "🧠 Reasoning",
                        "value": self._truncate_text(reasoning, 200),
                        "short": True
                    }
                ]
            }

            # Add timing information
            timestamp = agent_output.get('ts_iso', datetime.now(timezone.utc).isoformat())
            attachment["footer"] = f"NEO Trading System | {self._format_timestamp(timestamp)}"

            # Add orders if present
            if orders:
                orders_text = self._format_orders_for_slack(orders)
                attachment["fields"].append({
                    "title": "📋 Trading Orders",
                    "value": orders_text,
                    "short": False
                })

            slack_message = {
                "text": main_text,
                "attachments": [attachment],
                "username": "NEO Trading Bot",
                "icon_emoji": ":robot_face:"
            }

            return slack_message

        except Exception as e:
            logger.error(f"Slack formatting failed: {e}")
            # Return fallback message
            return {
                "text": "🚨 Error formatting trading alert",
                "attachments": [{
                    "color": "danger",
                    "text": f"Agent: {agent_output.get('agent_type', 'Unknown')}\nError: {str(e)}"
                }]
            }

    async def format_for_telegram(self, agent_output: Dict[str, Any]) -> tuple:
        """Format agent output for Telegram (returns message text and reply markup)"""
        try:
            # Extract key information
            agent_type = agent_output.get('agent_type', 'Unknown Agent')
            confidence = agent_output.get('confidence', 0.0)
            analysis = agent_output.get('analysis', 'No analysis provided')
            reasoning = agent_output.get('reasoning', 'No reasoning provided')
            orders = agent_output.get('orders', [])

            # Create header with emoji
            confidence_emoji = self._get_confidence_emoji(confidence)
            header = f"🎯 <b>NEO Trading Alert</b> {confidence_emoji}\n\n"

            # Agent information
            agent_name = self._format_agent_name(agent_type)
            message_parts = [
                header,
                f"🤖 <b>Agent:</b> {agent_name}",
                f"💪 <b>Confidence:</b> {confidence:.1%}",
                "",
                f"📊 <b>Analysis:</b>",
                self._truncate_text(analysis, 400),
                "",
                f"🧠 <b>Reasoning:</b>",
                self._truncate_text(reasoning, 300)
            ]

            # Add orders summary if present
            if orders:
                message_parts.extend(["", "💰 <b>Trading Recommendations:</b>"])
                orders_summary = self._format_orders_summary_for_telegram(orders)
                message_parts.append(orders_summary)

            # Add timestamp
            timestamp = agent_output.get('ts_iso', datetime.now(timezone.utc).isoformat())
            message_parts.extend([
                "",
                f"⏰ <i>{self._format_timestamp(timestamp)}</i>"
            ])

            message_text = "\n".join(message_parts)

            # Create inline keyboard with actions
            keyboard = []

            if orders:
                keyboard.append([
                    InlineKeyboardButton("📋 View Orders", callback_data="view_orders"),
                    InlineKeyboardButton("📈 Chart", callback_data="view_chart")
                ])

            keyboard.append([
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_analysis"),
                InlineKeyboardButton("⚠️ Risk Check", callback_data="risk_analysis")
            ])

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

            return message_text, reply_markup

        except Exception as e:
            logger.error(f"Telegram formatting failed: {e}")
            # Return fallback message
            error_text = (
                "🚨 <b>Error Formatting Alert</b>\n\n"
                f"Agent: {agent_output.get('agent_type', 'Unknown')}\n"
                f"Error: {str(e)}"
            )
            return error_text, None

    def _format_agent_name(self, agent_type: str) -> str:
        """Format agent type into readable name"""
        name_mapping = {
            'gpt_trend_analyzer': 'GPT Trend Analyzer',
            'gpt_risk_monitor': 'GPT Risk Monitor',
            'claude_strategy': 'Claude Strategy Agent',
            'claude_research': 'Claude Research Agent',
            'momentum_scanner': 'Momentum Scanner',
            'risk_monitor': 'Risk Monitor'
        }

        return name_mapping.get(agent_type, agent_type.replace('_', ' ').title())

    def _get_confidence_color(self, confidence: float) -> str:
        """Get color based on confidence level for Slack"""
        if confidence >= self.confidence_thresholds['high']:
            return "good"  # Green
        elif confidence >= self.confidence_thresholds['medium']:
            return "warning"  # Yellow
        else:
            return "#808080"  # Gray

    def _get_confidence_emoji(self, confidence: float) -> str:
        """Get emoji based on confidence level"""
        if confidence >= 0.9:
            return "🔥"
        elif confidence >= 0.8:
            return "💪"
        elif confidence >= 0.7:
            return "👍"
        elif confidence >= 0.6:
            return "👌"
        elif confidence >= 0.5:
            return "🤔"
        else:
            return "⚠️"

    def _format_orders_for_slack(self, orders: List[Dict[str, Any]]) -> str:
        """Format orders for Slack attachment"""
        if not orders:
            return "No orders generated"

        formatted_orders = []
        for i, order in enumerate(orders[:3], 1):  # Limit to 3 orders
            side_emoji = "📈" if order.get('side', '').lower() == 'buy' else "📉"
            symbol = order.get('symbol', 'N/A')
            side = order.get('side', 'N/A').upper()
            quantity = order.get('quantity', 'N/A')
            price = order.get('price')

            order_text = f"{side_emoji} *{side} {quantity} {symbol}*"
            if price:
                order_text += f" @ ${price:,.2f}"

            if order.get('reasoning'):
                order_text += f"\n   _{order['reasoning']}_"

            formatted_orders.append(order_text)

        if len(orders) > 3:
            formatted_orders.append(f"... and {len(orders) - 3} more orders")

        return "\n\n".join(formatted_orders)

    def _format_orders_summary_for_telegram(self, orders: List[Dict[str, Any]]) -> str:
        """Format orders summary for Telegram"""
        if not orders:
            return "   <i>No specific orders recommended</i>"

        summary_parts = []
        for order in orders[:2]:  # Show first 2 orders in summary
            side_emoji = "📈" if order.get('side', '').lower() == 'buy' else "📉"
            symbol = order.get('symbol', 'N/A')
            side = order.get('side', 'N/A').upper()
            quantity = order.get('quantity', 'N/A')
            price = order.get('price')

            order_summary = f"{side_emoji} <b>{side}</b> {quantity} {symbol}"
            if price:
                order_summary += f" @ <b>${price:,.2f}</b>"

            summary_parts.append(f"   • {order_summary}")

        if len(orders) > 2:
            summary_parts.append(f"   • <i>... and {len(orders) - 2} more</i>")

        return "\n".join(summary_parts)

    def _format_timestamp(self, timestamp_str: str) -> str:
        """Format ISO timestamp for display"""
        try:
            # Parse ISO timestamp
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except Exception:
            return timestamp_str

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to specified length with ellipsis"""
        if not text:
            return "N/A"

        if len(text) <= max_length:
            return text

        return text[:max_length - 3] + "..."

    def format_delivery_confirmation(self, delivery_info: Dict[str, Any]) -> str:
        """Format delivery confirmation message"""
        channel = delivery_info.get('channel', 'unknown')
        status = delivery_info.get('status', 'unknown')
        delivery_id = delivery_info.get('delivery_id', 'N/A')

        status_emoji = "✅" if status == "delivered" else "❌"

        return f"{status_emoji} Notification {status} to {channel.title()} (ID: {delivery_id})"

    def format_error_message(self, error_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format error message for notifications"""
        error_type = error_info.get('error_type', 'Unknown Error')
        error_details = error_info.get('details', 'No details available')

        return {
            "text": f"🚨 *{error_type}*",
            "attachments": [{
                "color": "danger",
                "text": error_details,
                "footer": f"NEO Trading System | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            }]
        }