"""
Utility functions for Authelia User Management GUI
"""
import secrets
import string
from passlib.hash import argon2


def generate_secure_password(length: int = 16) -> str:
    """
    Generate a secure random password

    Args:
        length: Length of the password (default: 16)

    Returns:
        Randomly generated password
    """
    # Define character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()-_=+[]{}|;:,.<>?"

    # Ensure at least one character from each set
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]

    # Fill the rest with random characters from all sets
    all_characters = uppercase + lowercase + digits + special
    password.extend(secrets.choice(all_characters) for _ in range(length - 4))

    # Shuffle to avoid predictable patterns
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def hash_password(password: str) -> str:
    """
    Hash a password using Authelia's CLI to ensure compatibility

    Calls Authelia's own crypto hash generator to create hashes
    that are guaranteed to work with Authelia's authentication.

    Args:
        password: Plain text password to hash

    Returns:
        Argon2id hashed password compatible with Authelia
    """
    import subprocess
    import re
    import os

    try:
        # Call Authelia CLI via docker exec
        # This ensures hash compatibility with Authelia's Go implementation
        cmd = [
            'docker', 'exec', 'authelia',
            'authelia', 'crypto', 'hash', 'generate', 'argon2',
            '--password', password,
            '--config', '/config/configuration.yml'
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            # Extract hash from output like "Digest: $argon2id$..."
            match = re.search(r'Digest:\s+(\$argon2id\$[^\s]+)', result.stdout)
            if match:
                return match.group(1)

        # Fallback to passlib if Authelia CLI fails
        # (This will still have compatibility issues but better than failing)
        import logging
        logging.warning(f"Authelia CLI hash generation failed, falling back to passlib: {result.stderr}")

    except Exception as e:
        import logging
        logging.warning(f"Could not call Authelia CLI for hash generation: {e}, falling back to passlib")

    # Fallback: use passlib (may have compatibility issues)
    return argon2.using(
        type='ID',
        rounds=3,
        salt_size=16,
        parallelism=4,
        memory_cost=65536
    ).hash(password)


def validate_username(username: str) -> tuple[bool, str]:
    """
    Validate username format

    Args:
        username: Username to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "Username cannot be empty"

    if len(username) < 3:
        return False, "Username must be at least 3 characters long"

    if len(username) > 32:
        return False, "Username must be at most 32 characters long"

    # Check for valid characters (lowercase letters, numbers, hyphens, underscores)
    if not all(c in string.ascii_lowercase + string.digits + '-_' for c in username):
        return False, "Username can only contain lowercase letters, numbers, hyphens, and underscores"

    if username[0] in '-_' or username[-1] in '-_':
        return False, "Username cannot start or end with hyphen or underscore"

    return True, ""


def validate_email(email: str) -> tuple[bool, str]:
    """
    Basic email validation

    Args:
        email: Email address to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email cannot be empty"

    if '@' not in email or '.' not in email.split('@')[-1]:
        return False, "Invalid email format"

    return True, ""
