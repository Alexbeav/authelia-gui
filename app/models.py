"""
Pydantic models for Authelia users.yml validation.

Implements strict validation:
- Username: lowercase alphanumeric with dots, hyphens, underscores
- Email: valid format, normalized to lowercase
- Groups: deduplicated, lowercase
"""
import re
from typing import List, Dict
from pydantic import BaseModel, Field, validator, EmailStr


# Username validation regex: lowercase letters/numbers, can contain . _ - but not at start/end
USERNAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9._-]{1,30}[a-z0-9]$')


class UserConfig(BaseModel):
    """Configuration for a single Authelia user."""

    password: str = Field(..., description="Bcrypt password hash")
    displayname: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., description="Email address (will be normalized)")
    groups: List[str] = Field(default_factory=list)

    @validator('password')
    def validate_password_hash(cls, v):
        """Ensure password is a valid bcrypt hash."""
        if not v or len(v) < 20:
            raise ValueError("Invalid password hash")
        # Bcrypt hashes start with $2a$, $2b$, or $2y$
        if not v.startswith(('$2a$', '$2b$', '$2y$')):
            raise ValueError("Password must be a bcrypt hash (starts with $2a$, $2b$, or $2y$)")
        return v

    @validator('email')
    def validate_email(cls, v):
        """Validate and normalize email to lowercase."""
        v = v.strip().lower()
        if not v:
            raise ValueError("Email cannot be empty")
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError("Invalid email format")
        return v

    @validator('groups')
    def validate_groups(cls, v):
        """Normalize groups: lowercase, deduplicate, remove empty."""
        if not isinstance(v, list):
            raise ValueError("Groups must be a list")
        # Normalize: lowercase, strip whitespace, remove empty strings
        normalized = [g.strip().lower() for g in v if g and g.strip()]
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for group in normalized:
            if group not in seen:
                seen.add(group)
                deduped.append(group)
        return deduped

    class Config:
        extra = 'forbid'  # Reject unknown fields


class UsersFile(BaseModel):
    """Root structure of users.yml file."""

    users: Dict[str, UserConfig] = Field(default_factory=dict)

    @validator('users')
    def validate_usernames(cls, v):
        """Validate all usernames match required pattern."""
        if not isinstance(v, dict):
            raise ValueError("Users must be a dictionary")

        for username in v.keys():
            if not USERNAME_PATTERN.match(username):
                raise ValueError(
                    f"Invalid username '{username}': must be lowercase alphanumeric, "
                    f"2-32 characters, can contain . _ - but not at start/end"
                )

        return v

    class Config:
        extra = 'forbid'


class CreateUserRequest(BaseModel):
    """Request model for creating a new user."""

    username: str = Field(..., min_length=2, max_length=32)
    email: str = Field(...)
    displayname: str = Field(..., min_length=1, max_length=100)
    password: str = Field(None, min_length=12, max_length=128)
    groups: List[str] = Field(default_factory=list)

    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        v = v.strip().lower()
        if not USERNAME_PATTERN.match(v):
            raise ValueError(
                "Username must be lowercase alphanumeric, 2-32 characters, "
                "can contain . _ - but not at start/end"
            )
        return v

    @validator('email')
    def validate_email(cls, v):
        """Validate and normalize email."""
        v = v.strip().lower()
        if '@' not in v or '.' not in v.split('@')[-1]:
            raise ValueError("Invalid email format")
        return v

    @validator('password')
    def validate_password(cls, v):
        """Validate password strength if provided."""
        if v is None:
            return v
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v

    @validator('groups')
    def validate_groups(cls, v):
        """Normalize groups."""
        normalized = [g.strip().lower() for g in v if g and g.strip()]
        # Deduplicate
        return list(dict.fromkeys(normalized))

    class Config:
        extra = 'forbid'


class UserListItem(BaseModel):
    """User information for list display."""

    username: str
    email: str
    displayname: str
    groups: List[str]
    has_totp: bool = False

    class Config:
        extra = 'allow'
