# Security

**Authentication, input validation, and security best practices for MCP servers.**

## Security Architecture

**Defense in Depth**: Multiple security layers protect against unauthorized access, input manipulation, and system abuse. Security is implemented at transport, authentication, authorization, input validation, and audit levels.

**Threat Model**: Protects against malicious agents, compromised credentials, injection attacks, data exfiltration, and denial of service attacks.

## Authentication Modes

### Local Development (No Auth)

**Use Case**: Development and testing environments
**Security Level**: None
**Configuration**:
```bash
AUTH_TOKEN=""  # Empty = no authentication
MCP_SERVER_MODE=stdio
```

**Risks**: No access control - suitable only for isolated development

### Service Mode (Bearer Token)

**Use Case**: Production deployments
**Security Level**: Medium
**Configuration**:
```bash
AUTH_TOKEN=your-secret-token-here
MCP_SERVER_MODE=http
```

**Implementation**:
```python
from fastapi import Request, HTTPException
import hmac
import hashlib
import secrets

class BearerTokenAuth:
    def __init__(self, secret_token: str):
        self.secret_token = secret_token
        
    async def verify_request(self, request: Request):
        """Verify Bearer token authentication."""
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(401, "Missing Authorization header")
            
        if not auth_header.startswith("Bearer "):
            raise HTTPException(401, "Invalid Authorization header format")
            
        token = auth_header[7:]  # Remove "Bearer "
        
        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(token, self.secret_token):
            raise HTTPException(401, "Invalid authentication token")

# Token generation for deployment
def generate_secure_token(length: int = 32) -> str:
    """Generate cryptographically secure token."""
    return secrets.token_urlsafe(length)
```

### Service Mode (HMAC Authentication)

**Use Case**: High-security production deployments
**Security Level**: High
**Configuration**:
```bash
API_KEY_HMAC_SECRET=your-hmac-secret-key
AUTH_MODE=hmac
```

### Required Headers

All tool requests must include authentication headers:

| Header | Required | Description |
|--------|----------|-------------|
| `X-Signature` | Yes | HMAC-SHA256 signature of request body |
| `X-Timestamp` | Yes | Unix timestamp (for replay protection) |
| `X-Nonce` | Yes | Unique request identifier |
| `Idempotency-Key` | Yes | Duplicate request prevention |
| `X-API-Version` | Yes | API version (e.g., "1.0.0") |

**Payload Limits:** 1MB maximum request size for all tool calls.

**Implementation**:
```python
import hmac
import hashlib
import time
from fastapi import Request, HTTPException

class HMACAuth:
    def __init__(self, secret_key: str, max_age_seconds: int = 300):
        self.secret_key = secret_key.encode()
        self.max_age_seconds = max_age_seconds

    async def verify_request(self, request: Request):
        """Verify HMAC signature authentication."""
        # Extract HMAC components from headers
        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")
        nonce = request.headers.get("X-Nonce")
        idempotency_key = request.headers.get("Idempotency-Key")
        api_version = request.headers.get("X-API-Version")

        if not all([timestamp, signature, nonce, idempotency_key, api_version]):
            raise HTTPException(401, "Missing required authentication headers")
            
        # Verify timestamp freshness
        try:
            request_time = int(timestamp)
            current_time = int(time.time())
            
            if abs(current_time - request_time) > self.max_age_seconds:
                raise HTTPException(401, "Request timestamp too old")
        except ValueError:
            raise HTTPException(401, "Invalid timestamp format")
            
        # Compute expected signature
        body = await request.body()
        message = f"{request.method}|{request.url.path}|{timestamp}|{body.decode()}"
        expected_signature = hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Verify signature
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(401, "Invalid HMAC signature")

# Client-side HMAC generation
def generate_hmac_headers(method: str, path: str, body: str, secret_key: str) -> dict:
    """Generate HMAC authentication headers for requests."""
    timestamp = str(int(time.time()))
    message = f"{method}|{path}|{timestamp}|{body}"
    signature = hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "X-Timestamp": timestamp,
        "X-Signature": signature
    }
```

## Input Hardening

### Size Limits

```python
from pydantic import BaseModel, validator
from typing import Any, Dict

class SecureToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]
    
    @validator('name')
    def validate_tool_name(cls, v):
        if len(v) > 100:
            raise ValueError("Tool name too long")
        if not v.replace('.', '').replace('_', '').isalnum():
            raise ValueError("Tool name contains invalid characters")
        return v
    
    @validator('arguments')
    def validate_arguments_size(cls, v):
        import json
        serialized = json.dumps(v)
        if len(serialized) > 1024 * 1024:  # 1MB limit
            raise ValueError("Arguments payload too large")
        return v

# Global input size middleware
from fastapi import Request

class InputSizeLimitMiddleware:
    def __init__(self, max_body_size: int = 10 * 1024 * 1024):  # 10MB
        self.max_body_size = max_body_size
        
    async def __call__(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > self.max_body_size:
            raise HTTPException(413, "Request payload too large")
            
        return await call_next(request)
```

### Numeric Range Validation

```python
from pydantic import BaseModel, validator, Field
from typing import Optional
from decimal import Decimal

class SecureFinancialInput(BaseModel):
    """Secure input validation for financial data."""
    
    quantity: Decimal = Field(..., gt=0, le=Decimal('1e12'))  # Max 1T units
    price: Optional[Decimal] = Field(None, gt=0, le=Decimal('1e9'))  # Max 1B price
    
    @validator('quantity')
    def validate_quantity_precision(cls, v):
        # Limit decimal precision to prevent DoS
        if v.as_tuple().exponent < -8:  # Max 8 decimal places
            raise ValueError("Quantity precision too high")
        return v
    
    @validator('price')
    def validate_price_precision(cls, v):
        if v and v.as_tuple().exponent < -6:  # Max 6 decimal places
            raise ValueError("Price precision too high")
        return v

# Custom validators for trading-specific fields
def validate_trading_symbol(symbol: str) -> str:
    """Validate trading symbol format and whitelist."""
    import re
    
    # Format validation
    if not re.match(r'^[A-Z]{3,6}(/[A-Z]{3,6})?$', symbol):
        raise ValueError(f"Invalid symbol format: {symbol}")
    
    # Symbol whitelist (prevent unauthorized instruments)
    ALLOWED_SYMBOLS = {
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
        "BTC/USD", "ETH/USD", "SPY", "QQQ", "IWM"
    }
    
    if symbol not in ALLOWED_SYMBOLS:
        raise ValueError(f"Symbol not authorized: {symbol}")
    
    return symbol

def validate_datetime_range(dt_str: str) -> str:
    """Validate datetime is within acceptable range."""
    from datetime import datetime, timezone, timedelta
    
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(f"Invalid datetime format: {dt_str}")
    
    now = datetime.now(timezone.utc)
    
    # Prevent requests for data too far in the past (>2 years)
    if dt < now - timedelta(days=730):
        raise ValueError("Date too far in the past")
    
    # Prevent requests for future data (>1 day ahead)
    if dt > now + timedelta(days=1):
        raise ValueError("Date too far in the future")
    
    return dt_str
```

### Enum Validation

```python
from enum import Enum
from pydantic import BaseModel, validator

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"

class Interval(str, Enum):
    ONE_MIN = "1m"
    FIVE_MIN = "5m"
    FIFTEEN_MIN = "15m"
    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"

class SecureOrderRequest(BaseModel):
    side: OrderSide
    order_type: OrderType
    interval: Interval
    
    @validator('*', pre=True)
    def reject_unknown_fields(cls, v, field):
        """Explicitly reject unknown enum values."""
        if isinstance(v, str):
            # Normalize case
            v = v.lower().strip()
        return v
```

## Secrets Management

### Environment Variable Security

```python
import os
from pathlib import Path
from cryptography.fernet import Fernet

class SecureConfig:
    """Secure configuration management."""
    
    def __init__(self):
        self.encryption_key = self._get_encryption_key()
        self.cipher = Fernet(self.encryption_key)
    
    def _get_encryption_key(self) -> bytes:
        """Get or generate encryption key for sensitive config."""
        key_file = Path(".encryption_key")
        
        if key_file.exists():
            return key_file.read_bytes()
        else:
            # Generate new key (production should use external key management)
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            key_file.chmod(0o600)  # Owner read-only
            return key
    
    def get_secret(self, env_var: str, encrypted: bool = False) -> str:
        """Securely retrieve secret from environment."""
        value = os.getenv(env_var)
        
        if not value:
            raise ValueError(f"Required secret {env_var} not found")
        
        if encrypted:
            try:
                return self.cipher.decrypt(value.encode()).decode()
            except Exception:
                raise ValueError(f"Failed to decrypt secret {env_var}")
        
        return value
    
    def encrypt_secret(self, plaintext: str) -> str:
        """Encrypt secret for storage."""
        return self.cipher.encrypt(plaintext.encode()).decode()

# Usage
config = SecureConfig()
auth_token = config.get_secret("AUTH_TOKEN")
db_password = config.get_secret("ENCRYPTED_DB_PASSWORD", encrypted=True)
```

### Log Sanitization

```python
import logging
import re
from typing import Any

class SanitizingFormatter(logging.Formatter):
    """Log formatter that sanitizes sensitive data."""
    
    SENSITIVE_PATTERNS = [
        (re.compile(r'"password":\s*"[^"]+"'), '"password": "[REDACTED]"'),
        (re.compile(r'"token":\s*"[^"]+"'), '"token": "[REDACTED]"'),
        (re.compile(r'"key":\s*"[^"]+"'), '"key": "[REDACTED]"'),
        (re.compile(r'Bearer [A-Za-z0-9+/=]+'), 'Bearer [REDACTED]'),
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        
        # Sanitize sensitive patterns
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            formatted = pattern.sub(replacement, formatted)
        
        return formatted

# Setup secure logging
def setup_secure_logging():
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(SanitizingFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    return logger
```

## SSRF Protection

### URL Validation

```python
import ipaddress
from urllib.parse import urlparse
from typing import Set

class SSRFProtection:
    """Server-Side Request Forgery protection."""
    
    BLOCKED_NETWORKS = {
        ipaddress.ip_network('127.0.0.0/8'),    # Loopback
        ipaddress.ip_network('10.0.0.0/8'),     # Private
        ipaddress.ip_network('172.16.0.0/12'),  # Private
        ipaddress.ip_network('192.168.0.0/16'), # Private
        ipaddress.ip_network('169.254.0.0/16'), # Link-local
        ipaddress.ip_network('::1/128'),        # IPv6 loopback
        ipaddress.ip_network('fc00::/7'),       # IPv6 private
    }
    
    ALLOWED_PROTOCOLS = {'http', 'https'}
    ALLOWED_PORTS = {80, 443, 8080, 8443}
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate URL against SSRF attacks."""
        parsed = urlparse(url)
        
        # Protocol validation
        if parsed.scheme not in cls.ALLOWED_PROTOCOLS:
            raise ValueError(f"Protocol {parsed.scheme} not allowed")
        
        # Host validation
        if not parsed.hostname:
            raise ValueError("Missing hostname in URL")
        
        # Resolve hostname to IP
        try:
            import socket
            ip_str = socket.gethostbyname(parsed.hostname)
            ip = ipaddress.ip_address(ip_str)
        except (socket.gaierror, ValueError):
            raise ValueError(f"Cannot resolve hostname: {parsed.hostname}")
        
        # Check against blocked networks
        for blocked_network in cls.BLOCKED_NETWORKS:
            if ip in blocked_network:
                raise ValueError(f"IP {ip} is in blocked network {blocked_network}")
        
        # Port validation
        port = parsed.port or (80 if parsed.scheme == 'http' else 443)
        if port not in cls.ALLOWED_PORTS:
            raise ValueError(f"Port {port} not allowed")
        
        return url

# HTTP client with SSRF protection
import aiohttp
from aiohttp import ClientSession, ClientTimeout

class SecureHTTPClient:
    def __init__(self, timeout_seconds: int = 30):
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.ssrf = SSRFProtection()
    
    async def get(self, url: str, **kwargs) -> dict:
        """Make secure HTTP GET request."""
        # Validate URL against SSRF
        safe_url = self.ssrf.validate_url(url)
        
        async with ClientSession(timeout=self.timeout) as session:
            async with session.get(safe_url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
```

## Rate Limiting

### Per-Client Rate Limiting

```python
import time
import asyncio
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, HTTPException

class SlidingWindowRateLimiter:
    """Sliding window rate limiter implementation."""
    
    def __init__(self, requests_per_minute: int, window_size_seconds: int = 60):
        self.rpm = requests_per_minute
        self.window_size = window_size_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed under rate limit."""
        async with self.lock:
            now = time.time()
            window_start = now - self.window_size
            
            # Clean old requests outside window
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if req_time > window_start
            ]
            
            # Check if under limit
            if len(self.requests[client_id]) >= self.rpm:
                return False
            
            # Record new request
            self.requests[client_id].append(now)
            return True
    
    def get_reset_time(self, client_id: str) -> int:
        """Get timestamp when rate limit resets for client."""
        if not self.requests[client_id]:
            return int(time.time())
        
        oldest_request = min(self.requests[client_id])
        return int(oldest_request + self.window_size)

class RateLimitMiddleware:
    def __init__(self, rpm: int = 1000):
        self.limiter = SlidingWindowRateLimiter(rpm)
    
    async def __call__(self, request: Request, call_next):
        client_id = self.get_client_id(request)
        
        if not await self.limiter.is_allowed(client_id):
            reset_time = self.limiter.get_reset_time(client_id)
            
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(self.limiter.rpm),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time - int(time.time()))
                }
            )
        
        return await call_next(request)
    
    def get_client_id(self, request: Request) -> str:
        """Extract client identifier for rate limiting."""
        # Priority order: API key > Auth token > IP address
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key[:8]}"
        
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token_hash = hashlib.md5(auth_header.encode()).hexdigest()
            return f"token:{token_hash[:8]}"
        
        return f"ip:{request.client.host}"
```

### Tool-Specific Rate Limiting

```python
class ToolRateLimiter:
    """Per-tool rate limiting with different limits."""
    
    def __init__(self):
        self.tool_limits = {
            "features.ohlcv_window": 100,        # 100/min - data intensive
            "risk.position_limits_check": 500,   # 500/min - lightweight
            "execution.sim_quote": 200,          # 200/min - moderate
            "storage.shared_state.get": 1000,    # 1000/min - very lightweight
            "storage.shared_state.set": 500,     # 500/min - moderate
        }
        
        self.limiters = {
            tool: SlidingWindowRateLimiter(limit)
            for tool, limit in self.tool_limits.items()
        }
    
    async def check_tool_limit(self, tool_name: str, client_id: str) -> bool:
        """Check if tool call is allowed for client."""
        limiter = self.limiters.get(tool_name)
        if not limiter:
            return True  # No limit configured
        
        return await limiter.is_allowed(f"{client_id}:{tool_name}")
```

## Error Surfaces

### Standardized Error Codes

```python
from enum import Enum
from typing import Optional, Dict, Any

class MCPErrorCode(str, Enum):
    # Input validation errors
    INVALID_ARGS = "MCP-001"
    UNAUTHORIZED = "MCP-002"
    BACKEND_UNAVAILABLE = "MCP-003"
    TIMEOUT = "MCP-004"
    IDEMPOTENCY_CONFLICT = "MCP-005"
    RATE_LIMIT_EXCEEDED = "MCP-006"
    
    # Server errors
    UNKNOWN_TOOL = "MCP-007"
    NO_HANDLER = "MCP-008"
    OUTPUT_SCHEMA_VIOLATION = "MCP-009"
    
    # Business logic errors
    INSUFFICIENT_DATA = "MCP-010"
    MISSING_CONFIGURATION = "MCP-011"
    INSUFFICIENT_LIQUIDITY = "MCP-012"
    KEY_NOT_FOUND = "MCP-013"
    STORAGE_QUOTA_EXCEEDED = "MCP-014"
    
    # Security errors
    INVALID_SYMBOL = "MCP-015"
    SSRF_BLOCKED = "MCP-016"
    PAYLOAD_TOO_LARGE = "MCP-017"
    
    # Internal errors
    INTERNAL_ERROR = "MCP-999"

class MCPSecurityError(Exception):
    """Security-related MCP error."""
    
    def __init__(self, code: MCPErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"{code}: {message}")

# Error response handling
def create_security_error_response(error: MCPSecurityError) -> dict:
    """Create standardized security error response."""
    return {
        "error": True,
        "code": error.code,
        "message": error.message,
        "details": error.details,
        "timestamp": datetime.utcnow().isoformat(),
        "security_event": True  # Flag for security monitoring
    }
```

### Security Event Logging

```python
import logging
from typing import Dict, Any

class SecurityLogger:
    """Specialized logger for security events."""
    
    def __init__(self):
        self.logger = logging.getLogger("security")
        self.logger.setLevel(logging.WARNING)
    
    def log_auth_failure(self, client_ip: str, reason: str, **kwargs):
        """Log authentication failure."""
        self.logger.warning(
            "Authentication failure",
            extra={
                "event_type": "auth_failure",
                "client_ip": client_ip,
                "reason": reason,
                "severity": "high",
                **kwargs
            }
        )
    
    def log_rate_limit_violation(self, client_id: str, tool: str, **kwargs):
        """Log rate limit violation."""
        self.logger.warning(
            "Rate limit exceeded",
            extra={
                "event_type": "rate_limit",
                "client_id": client_id,
                "tool": tool,
                "severity": "medium",
                **kwargs
            }
        )
    
    def log_ssrf_attempt(self, client_ip: str, blocked_url: str, **kwargs):
        """Log SSRF attempt."""
        self.logger.error(
            "SSRF attempt blocked",
            extra={
                "event_type": "ssrf_attempt",
                "client_ip": client_ip,
                "blocked_url": blocked_url,
                "severity": "critical",
                **kwargs
            }
        )
    
    def log_input_validation_failure(self, client_id: str, tool: str, violation: str, **kwargs):
        """Log input validation failure."""
        self.logger.warning(
            "Input validation failure",
            extra={
                "event_type": "input_validation",
                "client_id": client_id,
                "tool": tool,
                "violation": violation,
                "severity": "medium",
                **kwargs
            }
        )

# Security audit decorator
from functools import wraps

def security_audit(event_type: str):
    """Decorator to audit security-sensitive operations."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            security_logger = SecurityLogger()
            
            try:
                result = await func(*args, **kwargs)
                
                # Log successful security operation
                security_logger.logger.info(
                    f"Security operation completed: {event_type}",
                    extra={
                        "event_type": event_type,
                        "status": "success",
                        "function": func.__name__
                    }
                )
                
                return result
                
            except MCPSecurityError as e:
                # Log security error
                security_logger.logger.error(
                    f"Security operation failed: {event_type}",
                    extra={
                        "event_type": event_type,
                        "status": "failure",
                        "error_code": e.code,
                        "error_message": e.message,
                        "function": func.__name__
                    }
                )
                raise
                
        return wrapper
    return decorator
```

## Audit Requirements

### Audit Trail

```python
from datetime import datetime
from typing import Optional
import json

class AuditLogger:
    """Comprehensive audit logging for MCP operations."""
    
    def __init__(self, correlation_id: str):
        self.corr_id = correlation_id
        self.logger = logging.getLogger("audit")
    
    def log_tool_call(self, tool: str, client_id: str, duration_ms: int, 
                     status: str, input_size: int, output_size: int):
        """Audit tool execution."""
        self.logger.info(
            "Tool execution audit",
            extra={
                "corr_id": self.corr_id,
                "tool": tool,
                "client_id": client_id,
                "duration_ms": duration_ms,
                "status": status,
                "input_size_bytes": input_size,
                "output_size_bytes": output_size,
                "timestamp": datetime.utcnow().isoformat(),
                "audit_type": "tool_execution"
            }
        )
    
    def log_data_access(self, resource: str, client_id: str, action: str):
        """Audit data access operations."""
        self.logger.info(
            "Data access audit",
            extra={
                "corr_id": self.corr_id,
                "resource": resource,
                "client_id": client_id,
                "action": action,
                "timestamp": datetime.utcnow().isoformat(),
                "audit_type": "data_access"
            }
        )
    
    def log_configuration_change(self, setting: str, old_value: str, 
                               new_value: str, changed_by: str):
        """Audit configuration changes."""
        self.logger.warning(
            "Configuration change audit",
            extra={
                "corr_id": self.corr_id,
                "setting": setting,
                "old_value": old_value,  # Should be sanitized
                "new_value": new_value,  # Should be sanitized
                "changed_by": changed_by,
                "timestamp": datetime.utcnow().isoformat(),
                "audit_type": "config_change"
            }
        )

# Audit retention policy
CLASS_RETENTION_DAYS = {
    "tool_execution": 90,      # 3 months
    "data_access": 365,        # 1 year
    "security_events": 2555,   # 7 years
    "config_changes": 2555,    # 7 years
    "auth_events": 365,        # 1 year
}
```

---

**Next Steps**: Implement these security measures across all MCP servers. Regular security audits and penetration testing recommended.