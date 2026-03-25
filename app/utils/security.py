# ===========================================
# 安全相关工具函数
# ===========================================
"""
安全工具模块

包含:
- MD5签名计算和验证
- 随机字符串生成
- 密码处理
"""

import hashlib
import secrets
import string
from typing import Optional


def calculate_md5(data: str) -> str:
    """
    计算字符串的MD5哈希值
    
    Args:
        data: 原始字符串
    
    Returns:
        MD5哈希值(32位小写十六进制)
    
    示例:
        >>> calculate_md5("hello")
        '5d41402abc4b2a76b9719d911017c592'
    """
    return hashlib.md5(data.encode()).hexdigest()


def verify_md5_signature(
    data: str,
    signature: str,
    secret: Optional[str] = None
) -> bool:
    """
    验证MD5签名
    
    用于验证厂家Webhook请求的签名
    
    Args:
        data: 原始数据字符串
        signature: 待验证的签名
        secret: 签名密钥(可选，拼接在数据后面)
    
    Returns:
        签名是否有效
    
    示例:
        >>> data = '{"deviceCode": "TA001"}'
        >>> secret = "my_secret"
        >>> expected = calculate_md5(data + secret)
        >>> verify_md5_signature(data, expected, secret)
        True
    """
    if secret:
        calculated = calculate_md5(data + secret)
    else:
        calculated = calculate_md5(data)
    
    # 使用常量时间比较，防止时序攻击
    return secrets.compare_digest(calculated, signature)


def generate_random_string(
    length: int = 32,
    include_digits: bool = True,
    include_special: bool = False
) -> str:
    """
    生成随机字符串
    
    用于生成API密钥、随机密码等
    
    Args:
        length: 字符串长度
        include_digits: 是否包含数字
        include_special: 是否包含特殊字符
    
    Returns:
        随机字符串
    
    示例:
        >>> generate_random_string(16)
        'aB3dE7fG9hJ2kL5m'
        >>> generate_random_string(32, include_special=True)
        'aB#dE7fG9hJ@kL5mN8pQ1rS4tU6vW0xY'
    """
    # 基础字符集：大小写字母
    chars = string.ascii_letters
    
    if include_digits:
        chars += string.digits
    
    if include_special:
        chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    # 使用secrets模块生成安全的随机字符串
    return ''.join(secrets.choice(chars) for _ in range(length))


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """
    对密码进行哈希处理
    
    使用SHA256算法，配合盐值增强安全性
    
    Args:
        password: 原始密码
        salt: 盐值(可选，不传则自动生成)
    
    Returns:
        哈希后的密码(格式: salt$hash)
    
    示例:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
    """
    if salt is None:
        salt = generate_random_string(16, include_special=False)
    
    # 组合密码和盐值进行哈希
    hash_value = hashlib.sha256((password + salt).encode()).hexdigest()
    
    return f"{salt}${hash_value}"


def verify_password(password: str, hashed: str) -> bool:
    """
    验证密码
    
    Args:
        password: 待验证的密码
        hashed: 存储的哈希密码(格式: salt$hash)
    
    Returns:
        密码是否正确
    
    示例:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    try:
        salt, hash_value = hashed.split('$')
    except ValueError:
        return False
    
    calculated = hashlib.sha256((password + salt).encode()).hexdigest()
    
    return secrets.compare_digest(calculated, hash_value)


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    对敏感数据进行脱敏处理
    
    用于日志输出等场景
    
    Args:
        data: 原始数据
        visible_chars: 可见字符数
    
    Returns:
        脱敏后的数据
    
    示例:
        >>> mask_sensitive_data("13800138000")
        '1380********'
        >>> mask_sensitive_data("my_api_key_12345")
        'my_a***********'
    """
    if len(data) <= visible_chars:
        return '*' * len(data)
    
    return data[:visible_chars] + '*' * (len(data) - visible_chars)
