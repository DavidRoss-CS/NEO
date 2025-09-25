"""
MCP Client for interfacing with GPT/Claude agents via Model Context Protocol.
"""

import asyncio
import json
import os
from typing import Dict, Any, List, Optional, Union
import structlog
import openai
import anthropic
from datetime import datetime

logger = structlog.get_logger()

class MCPClient:
    """Model Context Protocol client for AI agent communication"""

    def __init__(self, openai_api_key: str = "", anthropic_api_key: str = ""):
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self.openai_client = None
        self.anthropic_client = None
        self.available_agents = {}
        self._initialized = False

    async def initialize(self):
        """Initialize MCP client and available agents"""
        try:
            # Initialize OpenAI client
            if self.openai_api_key:
                self.openai_client = openai.AsyncOpenAI(api_key=self.openai_api_key)
                self.available_agents.update({
                    "gpt_trend_analyzer": {
                        "type": "openai",
                        "model": "gpt-4",
                        "description": "GPT-4 powered trend analysis agent",
                        "capabilities": ["trend_analysis", "pattern_recognition", "sentiment_analysis"]
                    },
                    "gpt_risk_monitor": {
                        "type": "openai",
                        "model": "gpt-4",
                        "description": "GPT-4 powered risk monitoring agent",
                        "capabilities": ["risk_assessment", "portfolio_analysis", "volatility_prediction"]
                    }
                })

            # Initialize Anthropic client
            if self.anthropic_api_key:
                self.anthropic_client = anthropic.AsyncAnthropic(api_key=self.anthropic_api_key)
                self.available_agents.update({
                    "claude_strategy": {
                        "type": "anthropic",
                        "model": "claude-3-sonnet-20240229",
                        "description": "Claude powered trading strategy agent",
                        "capabilities": ["strategy_development", "backtesting", "optimization"]
                    },
                    "claude_research": {
                        "type": "anthropic",
                        "model": "claude-3-sonnet-20240229",
                        "description": "Claude powered market research agent",
                        "capabilities": ["fundamental_analysis", "news_analysis", "correlation_studies"]
                    }
                })

            self._initialized = True
            logger.info(
                "MCP client initialized",
                agents_count=len(self.available_agents),
                openai_enabled=bool(self.openai_api_key),
                anthropic_enabled=bool(self.anthropic_api_key)
            )

        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            raise

    async def run_agent(
        self,
        agent_id: str,
        signal_data: Dict[str, Any],
        context: Optional[List[Dict[str, str]]] = None,
        correlation_id: str = ""
    ) -> Dict[str, Any]:
        """Run specific agent with signal data and context"""
        if not self._initialized:
            raise RuntimeError("MCP client not initialized")

        if agent_id not in self.available_agents:
            raise ValueError(f"Agent {agent_id} not available")

        agent_config = self.available_agents[agent_id]
        agent_type = agent_config["type"]

        try:
            if agent_type == "openai":
                return await self._run_openai_agent(
                    agent_id, agent_config, signal_data, context, correlation_id
                )
            elif agent_type == "anthropic":
                return await self._run_anthropic_agent(
                    agent_id, agent_config, signal_data, context, correlation_id
                )
            else:
                raise ValueError(f"Unsupported agent type: {agent_type}")

        except Exception as e:
            logger.error(
                "Agent execution failed",
                agent_id=agent_id,
                agent_type=agent_type,
                error=str(e),
                corr_id=correlation_id
            )
            raise

    async def _run_openai_agent(
        self,
        agent_id: str,
        agent_config: Dict[str, Any],
        signal_data: Dict[str, Any],
        context: Optional[List[Dict[str, str]]],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Execute OpenAI GPT agent"""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized")

        # Build conversation context
        messages = []

        # System prompt based on agent type
        system_prompt = self._get_agent_system_prompt(agent_id, agent_config)
        messages.append({"role": "system", "content": system_prompt})

        # Add conversation context if provided
        if context:
            for ctx_msg in context[-10:]:  # Limit context to last 10 messages
                messages.append(ctx_msg)

        # Add current signal data
        user_message = self._format_signal_prompt(signal_data, agent_id)
        messages.append({"role": "user", "content": user_message})

        # Execute GPT request
        try:
            response = await self.openai_client.chat.completions.create(
                model=agent_config["model"],
                messages=messages,
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=2048,
                timeout=30.0
            )

            # Parse response
            content = response.choices[0].message.content
            result = self._parse_agent_response(content, agent_id)

            logger.info(
                "OpenAI agent completed",
                agent_id=agent_id,
                model=agent_config["model"],
                tokens_used=response.usage.total_tokens,
                corr_id=correlation_id
            )

            return result

        except Exception as e:
            logger.error(
                "OpenAI agent execution failed",
                agent_id=agent_id,
                error=str(e),
                corr_id=correlation_id
            )
            raise

    async def _run_anthropic_agent(
        self,
        agent_id: str,
        agent_config: Dict[str, Any],
        signal_data: Dict[str, Any],
        context: Optional[List[Dict[str, str]]],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Execute Anthropic Claude agent"""
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client not initialized")

        # Build conversation context
        messages = []

        # Add conversation context if provided
        if context:
            for ctx_msg in context[-10:]:  # Limit context to last 10 messages
                if ctx_msg["role"] != "system":  # Claude handles system separately
                    messages.append(ctx_msg)

        # Add current signal data
        user_message = self._format_signal_prompt(signal_data, agent_id)
        messages.append({"role": "user", "content": user_message})

        # System prompt
        system_prompt = self._get_agent_system_prompt(agent_id, agent_config)

        # Execute Claude request
        try:
            response = await self.anthropic_client.messages.create(
                model=agent_config["model"],
                system=system_prompt,
                messages=messages,
                max_tokens=2048,
                timeout=30.0
            )

            # Parse response
            content = response.content[0].text
            result = self._parse_agent_response(content, agent_id)

            logger.info(
                "Anthropic agent completed",
                agent_id=agent_id,
                model=agent_config["model"],
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                corr_id=correlation_id
            )

            return result

        except Exception as e:
            logger.error(
                "Anthropic agent execution failed",
                agent_id=agent_id,
                error=str(e),
                corr_id=correlation_id
            )
            raise

    def _get_agent_system_prompt(self, agent_id: str, agent_config: Dict[str, Any]) -> str:
        """Generate system prompt based on agent type"""
        base_prompt = """You are an expert trading analysis AI assistant. Your role is to analyze market signals and provide actionable trading insights.

Your response must be structured JSON with the following format:
{
    "analysis": "Detailed analysis of the market signal and conditions",
    "confidence": 0.85, // Confidence level from 0.0 to 1.0
    "reasoning": "Step-by-step reasoning for your analysis",
    "orders": [ // Optional trading orders based on analysis
        {
            "type": "limit",
            "side": "buy",
            "symbol": "BTCUSD",
            "quantity": 0.1,
            "price": 45000.0,
            "reasoning": "Entry point based on support level"
        }
    ]
}

Key Guidelines:
- Be conservative with confidence levels - only use >0.8 for very strong signals
- Always include detailed reasoning for your analysis
- Only suggest orders if there is a clear trading opportunity
- Consider risk management in all recommendations
- Use current market context in your analysis"""

        # Customize based on agent specialization
        if "trend_analyzer" in agent_id:
            base_prompt += "\n\nAs a trend analysis specialist, focus on identifying trend direction, strength, and potential reversal points."
        elif "risk_monitor" in agent_id:
            base_prompt += "\n\nAs a risk monitoring specialist, focus on identifying potential risks, volatility concerns, and portfolio protection strategies."
        elif "strategy" in agent_id:
            base_prompt += "\n\nAs a strategy specialist, focus on developing comprehensive trading strategies and optimizing entry/exit points."
        elif "research" in agent_id:
            base_prompt += "\n\nAs a research specialist, focus on fundamental analysis, market correlations, and broader economic context."

        return base_prompt

    def _format_signal_prompt(self, signal_data: Dict[str, Any], agent_id: str) -> str:
        """Format signal data into a prompt for the agent"""
        prompt = f"""Please analyze the following trading signal:

Signal Data:
{json.dumps(signal_data, indent=2)}

Current Analysis Context:
- Timestamp: {datetime.utcnow().isoformat()}Z
- Agent: {agent_id}
- Market Session: {self._get_market_session()}

Please provide your analysis following the structured JSON format specified in your system prompt."""

        return prompt

    def _parse_agent_response(self, content: str, agent_id: str) -> Dict[str, Any]:
        """Parse agent response and extract structured data"""
        try:
            # Try to extract JSON from response
            import re

            # Look for JSON block in response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
            else:
                # Fallback: treat entire response as analysis
                result = {
                    "analysis": content,
                    "confidence": 0.5,
                    "reasoning": "Unstructured response from agent",
                    "orders": []
                }

            # Validate required fields
            result.setdefault("analysis", "")
            result.setdefault("confidence", 0.0)
            result.setdefault("reasoning", "")
            result.setdefault("orders", [])

            # Ensure confidence is within valid range
            result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.0))))

            return result

        except Exception as e:
            logger.warning(
                "Failed to parse agent response as JSON",
                agent_id=agent_id,
                error=str(e)
            )
            # Return fallback response
            return {
                "analysis": content[:1000],  # Truncate if too long
                "confidence": 0.3,
                "reasoning": f"Failed to parse structured response: {str(e)}",
                "orders": []
            }

    def _get_market_session(self) -> str:
        """Determine current market session based on UTC time"""
        import datetime
        utc_hour = datetime.datetime.utcnow().hour

        if 0 <= utc_hour < 6:
            return "Asian"
        elif 6 <= utc_hour < 14:
            return "European"
        elif 14 <= utc_hour < 22:
            return "American"
        else:
            return "After Hours"

    async def cleanup(self):
        """Clean up MCP client resources"""
        # Close any persistent connections if needed
        if self.openai_client:
            await self.openai_client.close()

        logger.info("MCP client cleanup completed")