from django.test import SimpleTestCase

from user_app.forms import RegisterForm, ResetPasswordForm


class PasswordConfirmationFormTests(SimpleTestCase):
    def test_register_form_attaches_mismatch_error_to_confirmation_field(self):
        form = RegisterForm(data={
            "username": "form-user",
            "password": "Strong-Test-Password-123!",
            "confirm_password": "Different-Password-123!",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("confirm_password", form.errors)
        self.assertNotIn("__all__", form.errors)

    def test_reset_password_form_attaches_mismatch_error_to_confirmation_field(self):
        form = ResetPasswordForm(data={
            "password": "Strong-Test-Password-123!",
            "confirm_password": "Different-Password-123!",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("confirm_password", form.errors)
        self.assertNotIn("__all__", form.errors)
