import secrets
import string


class PasswordGenerator:
    """Generate cryptographically secure passwords and numeric recovery codes."""

    DEFAULT_LENGTH = 16

    UPPERCASE = string.ascii_uppercase
    LOWERCASE = string.ascii_lowercase
    NUMBERS = string.digits
    SYMBOLS = "!@#$%^&*_-+.="

    @classmethod
    def _validate_length(cls, length: int, *, minimum: int) -> None:
        if isinstance(length, bool) or not isinstance(length, int):
            raise TypeError("Length must be an integer.")
        if length < minimum:
            raise ValueError(f"Length must be at least {minimum} characters.")

    @classmethod
    def generate(cls, length: int = DEFAULT_LENGTH) -> str:
        """Generate a password with at least one of each character class."""
        cls._validate_length(length, minimum=cls.DEFAULT_LENGTH)

        required = [
            secrets.choice(cls.UPPERCASE),
            secrets.choice(cls.LOWERCASE),
            secrets.choice(cls.NUMBERS),
            secrets.choice(cls.SYMBOLS),
        ]
        alphabet = cls.UPPERCASE + cls.LOWERCASE + cls.NUMBERS + cls.SYMBOLS
        required.extend(secrets.choice(alphabet) for _ in range(length - len(required)))
        secrets.SystemRandom().shuffle(required)
        return "".join(required)

    @classmethod
    def generate_numeric(cls, length: int = DEFAULT_LENGTH) -> str:
        """Generate an ASCII numeric string, preserving any leading zeroes."""
        cls._validate_length(length, minimum=1)
        return "".join(secrets.choice(cls.NUMBERS) for _ in range(length))

    @classmethod
    def calculate_strength(cls, password: str) -> str:
        """Return a coarse UI estimate, not a measure of password entropy."""
        score = 0
        if any(char.islower() for char in password):
            score += 1
        if any(char.isupper() for char in password):
            score += 1
        if any(char.isdigit() for char in password):
            score += 1
        if any(char in cls.SYMBOLS for char in password):
            score += 1
        if len(password) >= cls.DEFAULT_LENGTH:
            score += 1

        return {
            0: "bad",
            1: "weak",
            2: "medium",
            3: "good",
            4: "strong",
            5: "extreme",
        }[score]
