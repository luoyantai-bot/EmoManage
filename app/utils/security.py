# ===========================================
# Security Utilities
# ===========================================
"""
Security utility functions.

Contains:
- MD5 signature calculation and verification
- Random string generation
- Password hashing
- Sensitive data masking
"""

import hashlib
import secrets
import string
from typing import Optional


# ===========================================
# Webhook Signature Verification
# ===========================================

def calculate_md5(data: str) -> str:
    """
    Calculate MD5 hash of a string.
    
    Args:
        data: Input string
    
    Returns:
        MD5 hash (32-char lowercase hex)
    
    Example:
        >>> calculate_md5("hello")
        '5d41402abc4b2a76b9719d911017c592'
    """
    return hashlib.md5(data.encode()).hexdigest()


def verify_webhook_sign(secret: str, timestamp: str, sign: str) -> bool:
    """
    Verify webhook signature from manufacturer.
    
    Signature algorithm: sign = md5(secret + timestamp)
    
    Args:
        secret: Webhook secret from environment variable
        timestamp: Unix timestamp from webhook payload
        sign: Signature to verify
    
    Returns:
        True if signature is valid
    
    Example:
        >>> secret = "my_webhook_secret"
        >>> timestamp = "1750759933"
        >>> expected_sign = calculate_md5(secret + timestamp)
        >>> verify_webhook_sign(secret, timestamp, expected_sign)
        True
    """
    if not secret or not timestamp or not sign:
        return False
    
    expected = calculate_md5(secret + timestamp)
    # Use constant-time comparison to prevent timing attacks
    return secrets.compare_digest(expected, sign)


def verify_md5_signature(
    data: str,
    signature: str,
    secret: Optional[str] = None
) -> bool:
    """
    Verify MD5 signature.
    
    For general MD5 signature verification.
    
    Args:
        data: Original data string
        signature: Signature to verify
        secret: Optional secret to append
    
    Returns:
        True if signature is valid
    """
    if secret:
        calculated = calculate_md5(data + secret)
    else:
        calculated = calculate_md5(data)
    
    return secrets.compare_digest(calculated, signature)


# ===========================================
# Random String Generation
# ===========================================

def generate_random_string(
    length: int = 32,
    include_digits: bool = True,
    include_special: bool = False
) -> str:
    """
    Generate a secure random string.
    
    Useful for API keys, random passwords, etc.
    
    Args:
        length: String length
        include_digits: Include digits
        include_special: Include special characters
    
    Returns:
        Random string
    
    Example:
        >>> generate_random_string(16)
        'aB3dE7fG9hJ2kL5m'
    """
    chars = string.ascii_letters
    
    if include_digits:
        chars += string.digits
    
    if include_special:
        chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    return ''.join(secrets.choice(chars) for _ in range(length))


# ===========================================
# Password Utilities
# ===========================================

def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    Hash a password with salt.
    
    Uses SHA256 with salt for security.
    
    Args:
        password: Plain password
        salt: Optional salt (auto-generated if not provided)
    
    Returns:
        Hashed password (format: salt$hash)
    
    Example:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
    """
    if salt is None:
        salt = generate_random_string(16, include_special=False)
    
    hash_value = hashlib.sha256((password + salt).encode()).hexdigest()
    
    return f"{salt}${hash_value}"


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: Password to verify
        hashed: Stored hash (format: salt$hash)
    
    Returns:
        True if password is correct
    """
    try:
        salt, hash_value = hashed.split('$')
    except ValueError:
        return False
    
    calculated = hashlib.sha256((password + salt).encode()).hexdigest()
    
    return secrets.compare_digest(calculated, hash_value)


# ===========================================
# Data Masking
# ===========================================

def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data for logging.
    
    Args:
        data: Original data
        visible_chars: Number of visible characters
    
    Returns:
        Masked data
    
    Example:
        >>> mask_sensitive_data("13800138000")
        '1380********'
    """
    if len(data) <= visible_chars:
        return '*' * len(data)
    
    return data[:visible_chars] + '*' * (len(data) - visible_chars)


def mask_phone(phone: str) -> str:
    """Mask phone number (show first 3 and last 4 digits)."""
    if not phone or len(phone) < 7:
        return mask_sensitive_data(phone, 2)
    
    return f"{phone[:3]}****{phone[-4:]}"


def mask_api_key(api_key: str) -> str:
    """Mask API key (show first 4 and last 4 characters)."""
    if not api_key or len(api_key) < 12:
        return mask_sensitive_data(api_key, 4)
    
    return f"{api_key[:4]}...{api_key[-4:]}"
