"""
Unit tests for user validation logic.

Tests:
- Username format validation
- Email validation
- Group normalization
- Password hash validation
"""
import pytest
from pydantic import ValidationError
from app.models import UserConfig, CreateUserRequest, UsersFile


class TestUsernameValidation:
    """Test username validation rules."""

    def test_valid_usernames(self):
        """Valid usernames should pass."""
        valid_usernames = [
            "ab",  # Minimum 2 chars
            "user123",
            "john.doe",
            "jane_smith",
            "test-user",
            "a1b2c3",
        ]

        for username in valid_usernames:
            request = CreateUserRequest(
                username=username,
                email="test@example.com",
                displayname="Test User",
                password="SecurePassword123!"
            )
            assert request.username == username.lower()

    def test_invalid_usernames(self):
        """Invalid usernames should fail."""
        invalid_usernames = [
            "a",  # Too short
            "UPPERCASE",  # Will be lowercased but test expects rejection
            ".startsdot",  # Starts with dot
            "endsdot.",  # Ends with dot
            "_startsunderscore",  # Starts with underscore
            "endsunderscore_",  # Ends with underscore
            "-startshyphen",  # Starts with hyphen
            "endshyphen-",  # Ends with hyphen
            "has spaces",  # Contains spaces
            "special!chars",  # Invalid special chars
        ]

        for username in invalid_usernames:
            with pytest.raises(ValidationError):
                CreateUserRequest(
                    username=username,
                    email="test@example.com",
                    displayname="Test User",
                    password="SecurePassword123!"
                )

    def test_username_normalization(self):
        """Usernames should be normalized to lowercase."""
        request = CreateUserRequest(
            username="TestUser123",
            email="test@example.com",
            displayname="Test User",
            password="SecurePassword123!"
        )
        assert request.username == "testuser123"


class TestEmailValidation:
    """Test email validation rules."""

    def test_valid_emails(self):
        """Valid emails should pass."""
        valid_emails = [
            "user@example.com",
            "john.doe@company.co.uk",
            "test+tag@domain.org",
        ]

        for email in valid_emails:
            request = CreateUserRequest(
                username="testuser",
                email=email,
                displayname="Test User",
                password="SecurePassword123!"
            )
            assert request.email == email.lower()

    def test_invalid_emails(self):
        """Invalid emails should fail."""
        invalid_emails = [
            "",
            "notanemail",
            "@nodomain.com",
            "noat.com",
            "no@domain",
        ]

        for email in invalid_emails:
            with pytest.raises(ValidationError):
                CreateUserRequest(
                    username="testuser",
                    email=email,
                    displayname="Test User",
                    password="SecurePassword123!"
                )

    def test_email_normalization(self):
        """Emails should be normalized to lowercase."""
        request = CreateUserRequest(
            username="testuser",
            email="Test.User@Example.COM",
            displayname="Test User",
            password="SecurePassword123!"
        )
        assert request.email == "test.user@example.com"


class TestGroupValidation:
    """Test group normalization."""

    def test_group_normalization(self):
        """Groups should be normalized and deduplicated."""
        config = UserConfig(
            password="$2b$12$abcdefghijklmnopqrstuvwxyz",
            displayname="Test User",
            email="test@example.com",
            groups=["Users", "ADMINS", "users", "developers"]
        )

        assert "users" in config.groups
        assert "admins" in config.groups
        assert "developers" in config.groups
        # Should only have 3 unique groups (users appears twice)
        assert len(config.groups) == 3

    def test_empty_groups_removed(self):
        """Empty/whitespace groups should be removed."""
        config = UserConfig(
            password="$2b$12$abcdefghijklmnopqrstuvwxyz",
            displayname="Test User",
            email="test@example.com",
            groups=["users", "", "  ", "admins", "\t"]
        )

        assert len(config.groups) == 2
        assert "users" in config.groups
        assert "admins" in config.groups


class TestPasswordHashValidation:
    """Test password hash validation."""

    def test_valid_bcrypt_hashes(self):
        """Valid bcrypt hashes should pass."""
        valid_hashes = [
            "$2a$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
            "$2b$10$xyzabcdefghijklmnopqrstuvwxyz123456789012345678",
            "$2y$12$1234567890abcdefghijklmnopqrstuvwxyz123456789012",
        ]

        for hash_value in valid_hashes:
            config = UserConfig(
                password=hash_value,
                displayname="Test User",
                email="test@example.com",
                groups=[]
            )
            assert config.password == hash_value

    def test_invalid_password_hashes(self):
        """Invalid password hashes should fail."""
        invalid_hashes = [
            "",
            "plaintext",
            "$2x$12$invalid",  # Invalid variant
            "tooshort",
        ]

        for hash_value in invalid_hashes:
            with pytest.raises(ValidationError):
                UserConfig(
                    password=hash_value,
                    displayname="Test User",
                    email="test@example.com",
                    groups=[]
                )


class TestPasswordValidation:
    """Test plaintext password validation for CreateUserRequest."""

    def test_minimum_password_length(self):
        """Passwords must be at least 12 characters."""
        with pytest.raises(ValidationError):
            CreateUserRequest(
                username="testuser",
                email="test@example.com",
                displayname="Test User",
                password="short"  # Too short
            )

    def test_valid_password_length(self):
        """Valid password lengths should pass."""
        request = CreateUserRequest(
            username="testuser",
            email="test@example.com",
            displayname="Test User",
            password="ValidPassword123!"
        )
        assert request.password == "ValidPassword123!"

    def test_optional_password(self):
        """Password should be optional (for auto-generation)."""
        request = CreateUserRequest(
            username="testuser",
            email="test@example.com",
            displayname="Test User",
            password=None
        )
        assert request.password is None


class TestUsersFileValidation:
    """Test UsersFile validation."""

    def test_valid_users_file(self):
        """Valid users file should pass validation."""
        users_data = {
            "alice": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Alice",
                email="alice@example.com",
                groups=["users"]
            ),
            "bob": UserConfig(
                password="$2b$12$xyzabcdefghijklmnopqrstuvwxyz123456789012345678",
                displayname="Bob",
                email="bob@example.com",
                groups=["admins"]
            )
        }

        users_file = UsersFile(users=users_data)
        assert len(users_file.users) == 2

    def test_invalid_username_in_file(self):
        """Invalid usernames in file should fail validation."""
        with pytest.raises(ValidationError):
            UsersFile(users={
                ".invaliduser": UserConfig(
                    password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                    displayname="Invalid",
                    email="invalid@example.com",
                    groups=[]
                )
            })
