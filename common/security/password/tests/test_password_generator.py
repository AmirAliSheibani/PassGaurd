from django.test import SimpleTestCase

from common.security.password.password_generator import PasswordGenerator


class PasswordGeneratorTests(SimpleTestCase):

    def test_generate_has_expected_length(self):
        password = PasswordGenerator.generate()

        self.assertEqual(
            len(password),
            PasswordGenerator.DEFAULT_LENGTH,
        )

    def test_generate_contains_required_character_types(self):
        password = PasswordGenerator.generate()

        self.assertTrue(
            any(char.isupper() for char in password)
        )

        self.assertTrue(
            any(char.islower() for char in password)
        )

        self.assertTrue(
            any(char.isdigit() for char in password)
        )

        self.assertTrue(
            any(char in PasswordGenerator.SYMBOLS for char in password)
        )

    def test_numeric_generator_returns_numeric_code(self):
        code = PasswordGenerator.generate_numeric(
            length=12,
        )

        self.assertEqual(
            len(code),
            12,
        )

        self.assertTrue(
            code.isdigit()
        )