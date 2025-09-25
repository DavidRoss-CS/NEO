"""
Agent Manager for orchestrating AI agent lifecycles and execution.
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import structlog

from .context_store import ContextStore
from .mcp_client import MCPClient

logger = structlog.get_logger()

class AgentManager:
    """Manages AI agent execution and lifecycle"""

    def __init__(
        self,
        context_store: ContextStore,
        mcp_client: MCPClient,
        timeout_sec: int = 30,
        max_context_length: int = 8192
    ):
        self.context_store = context_store
        self.mcp_client = mcp_client
        self.timeout_sec = timeout_sec
        self.max_context_length = max_context_length
        self.active_agents = {}
        self.agent_stats = {}

    async def run_agent(
        self,
        agent_type: str,
        signal_data: Dict[str, Any],
        context_key: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Execute agent with signal data and manage context"""
        agent_id = f"{agent_type}_{uuid.uuid4().hex[:8]}"

        try:
            # Mark agent as active
            self.active_agents[agent_id] = {
                "agent_type": agent_type,
                "context_key": context_key,
                "correlation_id": correlation_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "status": "running"
            }

            # Update agent stats
            self._update_agent_stats(agent_type, "started")

            # Get conversation context
            context_history = await self.context_store.get_context(context_key)

            # Prepare signal data with context
            enriched_signal_data = await self._enrich_signal_data(
                signal_data, context_history, correlation_id
            )

            # Execute agent with timeout
            result = await asyncio.wait_for(
                self.mcp_client.run_agent(
                    agent_id=agent_type,
                    signal_data=enriched_signal_data,
                    context=context_history,
                    correlation_id=correlation_id
                ),
                timeout=self.timeout_sec
            )

            # Store agent's response in context
            await self._store_agent_interaction(
                context_key, signal_data, result, agent_type
            )

            # Store agent session data
            await self.context_store.store_agent_session(
                agent_id,
                {
                    "agent_type": agent_type,
                    "correlation_id": correlation_id,
                    "signal_processed": True,
                    "confidence": result.get("confidence", 0.0),
                    "orders_generated": len(result.get("orders", [])),
                    "execution_time": self.active_agents[agent_id].get("execution_time", 0)
                }
            )

            # Mark as completed
            self.active_agents[agent_id]["status"] = "completed"
            self.active_agents[agent_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

            self._update_agent_stats(agent_type, "completed")

            # Add agent metadata to result
            result["agent_id"] = agent_id
            result["agent_type"] = agent_type
            result["context_key"] = context_key

            logger.info(
                "Agent execution completed",
                agent_id=agent_id,
                agent_type=agent_type,
                correlation_id=correlation_id,
                confidence=result.get("confidence"),
                orders_count=len(result.get("orders", []))
            )

            return result

        except asyncio.TimeoutError:
            self.active_agents[agent_id]["status"] = "timeout"
            self._update_agent_stats(agent_type, "timeout")

            logger.error(
                "Agent execution timeout",
                agent_id=agent_id,
                agent_type=agent_type,
                correlation_id=correlation_id,
                timeout_sec=self.timeout_sec
            )

            return {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "analysis": "Agent execution timed out",
                "confidence": 0.0,
                "reasoning": f"Agent failed to respond within {self.timeout_sec} seconds",
                "orders": []
            }

        except Exception as e:
            self.active_agents[agent_id]["status"] = "error"
            self.active_agents[agent_id]["error"] = str(e)
            self._update_agent_stats(agent_type, "error")

            logger.error(
                "Agent execution failed",
                agent_id=agent_id,
                agent_type=agent_type,
                correlation_id=correlation_id,
                error=str(e)
            )

            return {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "analysis": f"Agent execution failed: {str(e)}",
                "confidence": 0.0,
                "reasoning": f"Technical error during agent execution: {type(e).__name__}",
                "orders": []
            }

        finally:
            # Clean up active agent reference
            if agent_id in self.active_agents:
                execution_time = (
                    datetime.fromisoformat(
                        self.active_agents[agent_id].get(
                            "completed_at",
                            datetime.now(timezone.utc).isoformat()
                        ).replace("Z", "+00:00")
                    ) -
                    datetime.fromisoformat(
                        self.active_agents[agent_id]["started_at"].replace("Z", "+00:00")
                    )
                ).total_seconds()

                self.active_agents[agent_id]["execution_time"] = execution_time

                # Remove from active after a delay to allow monitoring
                asyncio.create_task(self._cleanup_agent_reference(agent_id, delay=300))

    async def _enrich_signal_data(
        self,
        signal_data: Dict[str, Any],
        context_history: List[Dict[str, str]],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Enrich signal data with additional context"""
        enriched = {
            **signal_data,
            "context": {
                "conversation_length": len(context_history),
                "has_previous_analysis": any(
                    msg.get("role") == "assistant" for msg in context_history
                ),
                "correlation_id": correlation_id,
                "enriched_at": datetime.now(timezone.utc).isoformat()
            }
        }

        # Add summary of recent context if available
        if context_history:
            recent_context = context_history[-3:]  # Last 3 messages
            enriched["context"]["recent_interactions"] = len(recent_context)

        return enriched

    async def _store_agent_interaction(
        self,
        context_key: str,
        signal_data: Dict[str, Any],
        agent_result: Dict[str, Any],
        agent_type: str
    ):
        """Store the agent interaction in context history"""
        try:
            # Store user message (signal data)
            user_message = {
                "role": "user",
                "content": f"Signal: {signal_data.get('instrument', 'Unknown')} - "
                         f"{signal_data.get('type', 'signal')} with strength "
                         f"{signal_data.get('strength', 0.0)}"
            }

            await self.context_store.store_context(context_key, user_message)

            # Store assistant response
            assistant_message = {
                "role": "assistant",
                "content": f"Analysis: {agent_result.get('analysis', 'No analysis provided')}\n"
                          f"Confidence: {agent_result.get('confidence', 0.0)}\n"
                          f"Reasoning: {agent_result.get('reasoning', 'No reasoning provided')}"
            }

            await self.context_store.store_context(context_key, assistant_message)

            logger.debug(
                "Agent interaction stored",
                context_key=context_key,
                agent_type=agent_type
            )

        except Exception as e:
            logger.warning(
                "Failed to store agent interaction",
                context_key=context_key,
                error=str(e)
            )

    def _update_agent_stats(self, agent_type: str, event: str):
        """Update agent statistics"""
        if agent_type not in self.agent_stats:
            self.agent_stats[agent_type] = {
                "started": 0,
                "completed": 0,
                "timeout": 0,
                "error": 0,
                "last_activity": None
            }

        self.agent_stats[agent_type][event] += 1
        self.agent_stats[agent_type]["last_activity"] = datetime.now(timezone.utc).isoformat()

    async def _cleanup_agent_reference(self, agent_id: str, delay: int = 300):
        """Clean up agent reference after delay"""
        await asyncio.sleep(delay)
        if agent_id in self.active_agents:
            del self.active_agents[agent_id]

    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific agent"""
        if agent_id in self.active_agents:
            return self.active_agents[agent_id]

        # Check if it's a stored session
        session_data = await self.context_store.get_agent_session(agent_id)
        if session_data:
            return {
                "agent_id": agent_id,
                "status": "completed",
                **session_data
            }

        return None

    async def list_active_agents(self) -> List[Dict[str, Any]]:
        """List all currently active agents"""
        return [
            {"agent_id": agent_id, **info}
            for agent_id, info in self.active_agents.items()
        ]

    async def get_agent_stats(self) -> Dict[str, Any]:
        """Get comprehensive agent statistics"""
        context_stats = await self.context_store.get_context_stats()

        return {
            "active_agents": len(self.active_agents),
            "agent_type_stats": self.agent_stats,
            "context_store_stats": context_stats,
            "available_agent_types": list(self.mcp_client.available_agents.keys()),
            "configuration": {
                "timeout_sec": self.timeout_sec,
                "max_context_length": self.max_context_length
            }
        }

    async def terminate_agent(self, agent_id: str, reason: str = "manual_termination") -> bool:
        """Terminate a running agent"""
        if agent_id not in self.active_agents:
            return False

        try:
            self.active_agents[agent_id]["status"] = "terminated"
            self.active_agents[agent_id]["termination_reason"] = reason
            self.active_agents[agent_id]["terminated_at"] = datetime.now(timezone.utc).isoformat()

            agent_type = self.active_agents[agent_id]["agent_type"]
            self._update_agent_stats(agent_type, "terminated")

            logger.info(
                "Agent terminated",
                agent_id=agent_id,
                reason=reason
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to terminate agent",
                agent_id=agent_id,
                error=str(e)
            )
            return False

    async def cleanup(self):
        """Clean up agent manager resources"""
        # Terminate any active agents
        for agent_id in list(self.active_agents.keys()):
            await self.terminate_agent(agent_id, "service_shutdown")

        logger.info("Agent manager cleanup completed")