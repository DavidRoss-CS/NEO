"""
Base broker adapter interface that all broker adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from .models import Order, Fill, Position, Account, OrderSide, OrderType

class BrokerAdapter(ABC):
    """Abstract base class for all broker adapters."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the broker adapter with configuration.

        Args:
            config: Configuration dictionary containing credentials and settings
        """
        self.config = config
        self.is_connected = False
        self.dry_run = config.get("dry_run", True)

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the broker API.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the broker API."""
        pass

    @abstractmethod
    async def submit_order(self, order: Order) -> Order:
        """
        Submit an order to the broker.

        Args:
            order: Order to submit

        Returns:
            Updated order with broker order ID and status

        Raises:
            BrokerError: If order submission fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Order:
        """
        Cancel an existing order.

        Args:
            order_id: ID of the order to cancel

        Returns:
            Updated order with cancelled status

        Raises:
            BrokerError: If order cancellation fails
        """
        pass

    @abstractmethod
    async def get_order(self, order_id: str) -> Order:
        """
        Get order details by ID.

        Args:
            order_id: ID of the order to retrieve

        Returns:
            Order details

        Raises:
            BrokerError: If order not found or retrieval fails
        """
        pass

    @abstractmethod
    async def get_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """
        Get list of orders, optionally filtered by symbol.

        Args:
            symbol: Optional symbol filter

        Returns:
            List of orders
        """
        pass

    @abstractmethod
    async def get_fills(self, order_id: Optional[str] = None) -> List[Fill]:
        """
        Get list of fills, optionally filtered by order ID.

        Args:
            order_id: Optional order ID filter

        Returns:
            List of fills
        """
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """
        Get current positions.

        Returns:
            List of positions
        """
        pass

    @abstractmethod
    async def get_account(self) -> Account:
        """
        Get account information.

        Returns:
            Account details
        """
        pass

    @abstractmethod
    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get current market data for a symbol.

        Args:
            symbol: Symbol to get market data for

        Returns:
            Market data dictionary with price, bid, ask, volume, etc.
        """
        pass

    async def is_market_open(self) -> bool:
        """
        Check if the market is currently open.

        Returns:
            True if market is open, False otherwise
        """
        # Default implementation - should be overridden by specific adapters
        from datetime import datetime, time
        now = datetime.now()

        # Simple US market hours check (9:30 AM - 4:00 PM ET, weekdays)
        if now.weekday() >= 5:  # Weekend
            return False

        market_open = time(9, 30)
        market_close = time(16, 0)
        current_time = now.time()

        return market_open <= current_time <= market_close

class BrokerError(Exception):
    """Base exception for broker adapter errors."""

    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}

class ConnectionError(BrokerError):
    """Raised when broker connection fails."""
    pass

class AuthenticationError(BrokerError):
    """Raised when broker authentication fails."""
    pass

class OrderError(BrokerError):
    """Raised when order operations fail."""
    pass

class InsufficientFundsError(BrokerError):
    """Raised when account has insufficient funds for an order."""
    pass

class MarketClosedError(BrokerError):
    """Raised when attempting to trade while market is closed."""
    pass