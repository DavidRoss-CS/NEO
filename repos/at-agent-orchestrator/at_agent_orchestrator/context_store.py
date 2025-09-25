"""
Context store for persistent agent conversations using Redis.
"""

import json
import redis
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

class ContextStore:
    """Redis-based context storage for agent conversations"""

    def __init__(self, redis_url: str = "redis://localhost:6379", ttl_hours: int = 24):
        self.redis_url = redis_url
        self.ttl_seconds = ttl_hours * 3600
        self.redis_client = None
        self._initialized = False

    async def initialize(self):
        """Initialize Redis connection"""
        try:
            # Create Redis connection pool
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=10
            )

            # Test connection
            await self._redis_ping()

            self._initialized = True
            logger.info("Context store initialized", redis_url=self.redis_url)

        except Exception as e:
            logger.error(f"Failed to initialize context store: {e}")
            raise

    async def _redis_ping(self):
        """Ping Redis to test connection (async wrapper)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.redis_client.ping)

    async def store_context(
        self,
        context_key: str,
        message: Dict[str, str],
        max_messages: int = 50
    ):
        """Store a message in the conversation context"""
        if not self._initialized:
            raise RuntimeError("Context store not initialized")

        try:
            loop = asyncio.get_event_loop()

            # Add timestamp to message
            message_with_timestamp = {
                **message,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Store message in Redis list
            await loop.run_in_executor(
                None,
                self.redis_client.lpush,
                f"context:{context_key}",
                json.dumps(message_with_timestamp)
            )

            # Trim list to max_messages
            await loop.run_in_executor(
                None,
                self.redis_client.ltrim,
                f"context:{context_key}",
                0, max_messages - 1
            )

            # Set expiration
            await loop.run_in_executor(
                None,
                self.redis_client.expire,
                f"context:{context_key}",
                self.ttl_seconds
            )

            logger.debug(
                "Context stored",
                context_key=context_key,
                message_role=message.get("role"),
                content_length=len(message.get("content", ""))
            )

        except Exception as e:
            logger.error(
                "Failed to store context",
                context_key=context_key,
                error=str(e)
            )
            raise

    async def get_context(self, context_key: str) -> List[Dict[str, str]]:
        """Retrieve conversation context for a key"""
        if not self._initialized:
            raise RuntimeError("Context store not initialized")

        try:
            loop = asyncio.get_event_loop()

            # Get messages from Redis (most recent first)
            messages_json = await loop.run_in_executor(
                None,
                self.redis_client.lrange,
                f"context:{context_key}",
                0, -1
            )

            # Parse and reverse to get chronological order
            messages = []
            for msg_json in reversed(messages_json):
                try:
                    msg = json.loads(msg_json)
                    # Remove timestamp for agent consumption
                    if "timestamp" in msg:
                        del msg["timestamp"]
                    messages.append(msg)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in context: {msg_json}")
                    continue

            logger.debug(
                "Context retrieved",
                context_key=context_key,
                message_count=len(messages)
            )

            return messages

        except Exception as e:
            logger.error(
                "Failed to retrieve context",
                context_key=context_key,
                error=str(e)
            )
            return []

    async def clear_context(self, context_key: str):
        """Clear context for a specific key"""
        if not self._initialized:
            raise RuntimeError("Context store not initialized")

        try:
            loop = asyncio.get_event_loop()

            await loop.run_in_executor(
                None,
                self.redis_client.delete,
                f"context:{context_key}"
            )

            logger.info("Context cleared", context_key=context_key)

        except Exception as e:
            logger.error(
                "Failed to clear context",
                context_key=context_key,
                error=str(e)
            )
            raise

    async def store_agent_session(
        self,
        agent_id: str,
        session_data: Dict[str, Any]
    ):
        """Store agent session metadata"""
        if not self._initialized:
            raise RuntimeError("Context store not initialized")

        try:
            loop = asyncio.get_event_loop()

            session_key = f"session:{agent_id}"
            session_json = json.dumps({
                **session_data,
                "last_updated": datetime.utcnow().isoformat()
            })

            await loop.run_in_executor(
                None,
                self.redis_client.setex,
                session_key,
                self.ttl_seconds,
                session_json
            )

            logger.debug(
                "Agent session stored",
                agent_id=agent_id,
                session_data_keys=list(session_data.keys())
            )

        except Exception as e:
            logger.error(
                "Failed to store agent session",
                agent_id=agent_id,
                error=str(e)
            )
            raise

    async def get_agent_session(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve agent session metadata"""
        if not self._initialized:
            raise RuntimeError("Context store not initialized")

        try:
            loop = asyncio.get_event_loop()

            session_key = f"session:{agent_id}"
            session_json = await loop.run_in_executor(
                None,
                self.redis_client.get,
                session_key
            )

            if session_json:
                session_data = json.loads(session_json)
                logger.debug(
                    "Agent session retrieved",
                    agent_id=agent_id,
                    last_updated=session_data.get("last_updated")
                )
                return session_data
            else:
                return None

        except Exception as e:
            logger.error(
                "Failed to retrieve agent session",
                agent_id=agent_id,
                error=str(e)
            )
            return None

    async def list_active_contexts(self, pattern: str = "context:*") -> List[str]:
        """List active context keys"""
        if not self._initialized:
            raise RuntimeError("Context store not initialized")

        try:
            loop = asyncio.get_event_loop()

            keys = await loop.run_in_executor(
                None,
                self.redis_client.keys,
                pattern
            )

            # Strip the context: prefix
            context_keys = [key.replace("context:", "") for key in keys]

            logger.debug(
                "Active contexts listed",
                context_count=len(context_keys)
            )

            return context_keys

        except Exception as e:
            logger.error(
                "Failed to list active contexts",
                error=str(e)
            )
            return []

    async def get_context_stats(self) -> Dict[str, Any]:
        """Get statistics about stored contexts"""
        if not self._initialized:
            raise RuntimeError("Context store not initialized")

        try:
            loop = asyncio.get_event_loop()

            # Get Redis info
            info = await loop.run_in_executor(None, self.redis_client.info)

            # Count contexts and sessions
            context_keys = await loop.run_in_executor(
                None,
                self.redis_client.keys,
                "context:*"
            )

            session_keys = await loop.run_in_executor(
                None,
                self.redis_client.keys,
                "session:*"
            )

            stats = {
                "total_contexts": len(context_keys),
                "total_sessions": len(session_keys),
                "redis_memory_used": info.get("used_memory_human", "unknown"),
                "redis_connected_clients": info.get("connected_clients", 0),
                "ttl_hours": self.ttl_seconds / 3600
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get context stats: {e}")
            return {"error": str(e)}

    async def health_check(self) -> bool:
        """Check if context store is healthy"""
        if not self._initialized:
            return False

        try:
            await self._redis_ping()
            return True
        except Exception:
            return False

    async def cleanup(self):
        """Clean up context store resources"""
        if self.redis_client:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.redis_client.close)
            except Exception as e:
                logger.warning(f"Error during Redis cleanup: {e}")

        logger.info("Context store cleanup completed")