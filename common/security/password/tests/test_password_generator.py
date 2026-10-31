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
    def test_numeric_generator_rejects_non_positive_and_non_integer_lengths(self):
        for invalid_length in (0, -1, True, 1.5, "12"):
            with self.subTest(length=invalid_length):
                with self.assertRaises(ValueError):
                    PasswordGenerator.generate_numeric(length=invalid_length)

    def test_regular_generator_rejects_boolean_and_non_integer_lengths(self):
        for invalid_length in (True, 16.5, "16"):
            with self.subTest(length=invalid_length):
                with self.assertRaises(ValueError):
                    PasswordGenerator.generate(length=invalid_length)
