"""
Data models for Authelia User Management GUI
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr


class User(BaseModel):
    """User model representing an Authelia user"""
    username: str
    email: EmailStr
    displayname: str
    groups: List[str] = []
    password_hash: str
    has_totp: bool = False
    totp_last_used: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "displayname": "John Doe",
                "groups": ["users"],
                "password_hash": "$argon2id$...",
                "has_totp": True,
                "totp_last_used": "2025-11-01T12:00:00"
            }
        }


class TOTPConfig(BaseModel):
    """TOTP configuration for a user"""
    username: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    algorithm: str = "SHA1"
    digits: int = 6
    period: int = 30


class UserDetail(BaseModel):
    """Extended user information including 2FA status"""
    username: str
    email: str
    displayname: str
    groups: List[str]
    has_totp: bool
    totp_last_used: Optional[str] = None
    totp_created_at: Optional[str] = None
