import secrets
import string


class PasswordGenerator:
    """
    Generates secure random passwords.
    """

    DEFAULT_LENGTH = 16

    UPPERCASE = string.ascii_uppercase
    LOWERCASE = string.ascii_lowercase
    NUMBERS = string.digits
    SYMBOLS = "!@#$%^&*_-+=."

    @classmethod
    def generate(cls, length: int = DEFAULT_LENGTH) -> str:
        if length < cls.DEFAULT_LENGTH:
            raise ValueError(
                f"Password length must be at least {cls.DEFAULT_LENGTH} characters"
            )

        required = [
            secrets.choice(cls.UPPERCASE),
            secrets.choice(cls.LOWERCASE),
            secrets.choice(cls.NUMBERS),
            secrets.choice(cls.SYMBOLS),
        ] # Example: ["K", "m", "7", "@"]

        all_characters = (
            cls.UPPERCASE
            + cls.LOWERCASE
            + cls.NUMBERS
            + cls.SYMBOLS
        ) # Result: ["ABCDE...abcde...01234...!@#$..."]

        remaining = [
            secrets.choice(all_characters)
            for _ in range(length - len(required)) # 8 - 4
        ]

        password_chars = required + remaining # 4 + 4
        shuffled_password = []

        while password_chars:
            random_index = secrets.randbelow(len(password_chars))
            shuffled_password.append(
                password_chars.pop(random_index)
            )

        return "".join(shuffled_password)


    @classmethod
    def calculate_strength(cls, password: str) -> str:
        """
        Calculates the strength of a password.
        """
        score = 0

        if any(char.islower() for char in password):
            score += 1

        if any(char.isupper() for char in password):
            score += 1

        if any(char.isdigit() for char in password):
            score += 1

        if any(char in cls.SYMBOLS for char in password):
            score += 1

        if len(password) >= 16:
            score += 1

        levels = {
            0: "bad",
            1: "weak",
            2: "medium",
            3: "good",
            4: "strong",
            5: "extreme",
        }

        return levels.get(score, "bad")
