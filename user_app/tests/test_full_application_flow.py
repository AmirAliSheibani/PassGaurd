"""End-to-end integration test for PassGuard.

Place this file at:
    user_app/tests/test_full_application_flow.py

The test uses Django's real URL resolver and test Client, but deliberately
bypasses template rendering because the HTML templates have not been built yet.
It still exercises the actual forms, views, services, authentication/session
middleware, and database writes.
"""

import re
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.http import HttpResponse
from django.template.response import SimpleTemplateResponse
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, URLPattern, URLResolver, get_resolver, reverse
from django.utils.text import slugify

from credential_app.models import Credential, CredentialHistory
from user_app.models import BackupCode
from vault_app.models import Category, Vault


TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "passguard-e2e-default",
    },
    "security": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "passguard-e2e-security",
    },
}



def _skip_template_html(response):
    """Mark a TemplateResponse rendered without loading any HTML template."""
    if not response.is_rendered:
        response.content = b""
        response._is_rendered = True
    return response



@override_settings(CACHES=TEST_CACHES)
class FullApplicationFlowTests(TestCase):
    """A single journey through registration, recovery, vaults and credentials."""

    username = "e2e_passguard_user"
    initial_password = "Initial-Master-Password-2026!"
    replacement_password = "Replacement-Master-Password-2026!"
    credential_password = "GitHub-Password-2026!"
    rotated_password = "GitHub-Rotated-Password-2026!"

    def setUp(self):
        self.rendered_contexts = []
        self._render_patchers = []

        # Some views call django.shortcuts.render directly. Replace only that
        # rendering function; do not replace the view, form, or service.
        for module_path in (
            "user_app.views.render",
            "vault_app.views.render",
            "credential_app.views.render",
        ):
            patcher = patch(
                module_path,
                new=self._render_without_html,
                create=True,
            )
            patcher.start()
            self._render_patchers.append(patcher)
            self.addCleanup(patcher.stop)

        # TemplateView / DetailView use TemplateResponse instead of the
        # shortcuts.render function. Prevent only the final HTML rendering.
        template_patcher = patch(
            "django.template.response.SimpleTemplateResponse.render",
            new=_skip_template_html,
        )
        template_patcher.start()
        self.addCleanup(template_patcher.stop)

        # Clear local caches so rate-limit/cooldown state cannot leak between
        # tests. With TEST_CACHES, this does not require a running Redis server.
        for cache_name in TEST_CACHES:
            caches[cache_name].clear()

        self.user = None
        self.personal_vault = None
        self.work_vault = None
        self.category = None
        self.credential = None
        self.backup_codes = []

    # ------------------------------------------------------------------
    # Template-free response helpers
    # ------------------------------------------------------------------

    def _render_without_html(
        self,
        request,
        template_name,
        context=None,
        content_type=None,
        status=None,
        using=None,
    ):
        context = context or {}
        self.rendered_contexts.append(context)
        response = HttpResponse(
            content=b"",
            content_type=content_type,
            status=status or 200,
        )
        response.context_data = context
        response.template_name = template_name
        return response

    # ------------------------------------------------------------------
    # URL discovery helpers
    # ------------------------------------------------------------------

    def _named_url_patterns(self, patterns=None, namespace_parts=()):
        """Yield (URLPattern, qualified_name) from the active URLconf."""
        if patterns is None:
            patterns = get_resolver().url_patterns

        for entry in patterns:
            if isinstance(entry, URLResolver):
                namespace = entry.namespace or entry.app_name
                child_parts = namespace_parts
                if namespace:
                    child_parts = (*namespace_parts, namespace)
                yield from self._named_url_patterns(entry.url_patterns, child_parts)
                continue

            if isinstance(entry, URLPattern) and entry.name:
                qualified_name = ":".join((*namespace_parts, entry.name))
                yield entry, qualified_name

    def _route_value(
        self,
        parameter_name,
        converter,
        view_name,
        user=None,
        vault=None,
        credential=None,
        category=None,
        extra=None,
    ):
        """Map common URL parameters to the object for the current workflow."""
        extra = extra or {}
        if parameter_name in extra:
            return extra[parameter_name]

        key = parameter_name.lower()
        converter_name = converter.__class__.__name__
        is_integer = converter_name == "IntConverter"
        is_slug = converter_name == "SlugConverter"
        view_lower = view_name.lower()

        if "username" in key or key in {"user_name", "owner_name"}:
            return getattr(user, "username", None)

        if key in {"user_id", "uid"} or (key == "user" and is_integer):
            return getattr(user, "pk", None)

        if "credential" in key:
            return getattr(credential, "pk", None)

        if "category" in key:
            if is_integer:
                return getattr(category, "pk", None)
            if category is not None:
                return slugify(category.name)

        if "vault" in key:
            if is_integer:
                return getattr(vault, "pk", None)
            return getattr(vault, "slug", None)

        if key in {"pk", "id"} or key.endswith("_pk"):
            if "credential" in view_lower:
                return getattr(credential, "pk", None)
            if "category" in view_lower:
                return getattr(category, "pk", None)
            if "vault" in view_lower:
                return getattr(vault, "pk", None)
            if "user" in view_lower:
                return getattr(user, "pk", None)

        if is_slug:
            if "category" in view_lower and category is not None:
                return slugify(category.name)
            return getattr(vault, "slug", None)

        if converter_name == "StringConverter" and user is not None:
            return user.username

        return None

    def _url_for_view(
        self,
        view_name,
        *,
        user=None,
        vault=None,
        credential=None,
        category=None,
        extra=None,
    ):
        """Reverse a route by its View class name, independent of URL name."""
        candidates = []
        for pattern, qualified_name in self._named_url_patterns():
            callback = pattern.callback
            view_class = getattr(callback, "view_class", None)
            actual_name = (
                view_class.__name__
                if view_class is not None
                else getattr(callback, "__name__", "")
            )
            if actual_name != view_name:
                continue

            converters = getattr(pattern.pattern, "converters", {})
            kwargs = {}
            missing = False
            for parameter_name, converter in converters.items():
                value = self._route_value(
                    parameter_name,
                    converter,
                    actual_name,
                    user=user,
                    vault=vault,
                    credential=credential,
                    category=category,
                    extra=extra,
                )
                if value is None:
                    missing = True
                    break
                kwargs[parameter_name] = value

            if missing:
                candidates.append(f"{qualified_name} (missing route parameter value)")
                continue

            try:
                return reverse(qualified_name, kwargs=kwargs or None)
            except NoReverseMatch:
                candidates.append(qualified_name)

        available = sorted(
            {
                (
                    getattr(getattr(pattern.callback, "view_class", None), "__name__", None)
                    or getattr(pattern.callback, "__name__", "")
                )
                for pattern, _ in self._named_url_patterns()
            }
        )
        self.fail(
            f"Could not reverse a URL for view {view_name!r}. "
            f"Tried: {candidates}. Available views/functions: {available}"
        )

    def _find_recovery_view_name(self):
        """Find the user-facing backup-code recovery endpoint in the URLconf."""
        names = []
        for pattern, _ in self._named_url_patterns():
            callback = pattern.callback
            view_class = getattr(callback, "view_class", None)
            name = (
                view_class.__name__
                if view_class is not None
                else getattr(callback, "__name__", "")
            )
            lowered = name.lower()
            if not any(token in lowered for token in ("recover", "recovery", "backupcode")):
                continue
            if any(token in lowered for token in ("setup", "reset", "regenerat", "confirm", "download")):
                continue
            names.append(name)

        # Prefer a clearly named recovery view over a generic backup-code view.
        def recovery_priority(name):
            lowered = name.lower()
            if "backup" in lowered and any(token in lowered for token in ("recover", "recovery", "verify", "validate")):
                return 0
            if "recover" in lowered or "recovery" in lowered:
                return 1
            return 2

        names.sort(key=lambda name: (recovery_priority(name), name))
        return names[0] if names else None

    # ------------------------------------------------------------------
    # Form payloads
    # Extra aliases are deliberate: Django forms ignore unknown POST keys,
    # while this keeps the test compatible with common password field names.
    # ------------------------------------------------------------------

    def _registration_payload(self):
        return {
            "username": self.username,
            "email": "e2e@example.test",
            "password": self.initial_password,
            "confirm_password": self.initial_password,
            "password_confirm": self.initial_password,
            "password_confirmation": self.initial_password,
            "master_password": self.initial_password,
            "confirm_master_password": self.initial_password,
            "password1": self.initial_password,
            "password2": self.initial_password,
        }

    def _vault_payload(self, name):
        return {
            "name": name,
            "slug": slugify(name),
            "description": f"Created by end-to-end test: {name}",
            "is_default": "",
        }

    def _category_payload(self, name):
        return {
            "name": name,
            "color": "#4F46E5",
            "hex_color": "#4F46E5",
        }

    def _credential_payload(self):
        return {
            "service_name": "GitHub",
            "service_url": "https://github.com/",
            "login_username": "e2e-login",
            "login_email": "e2e-login@example.test",
            "password": self.credential_password,
            "confirm_password": self.credential_password,
            "category": str(self.category.pk),
            "category_id": str(self.category.pk),
            "notes": "Created by the full application journey test.",
        }

    # ------------------------------------------------------------------
    # Backup-code extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_backup_code(value):
        if not isinstance(value, str):
            return False
        digits = re.sub(r"\D", "", value)
        return 8 <= len(digits) <= 16 and bool(re.fullmatch(r"[\d\s-]+", value))

    def _find_backup_code_lists(self, value):
        """Recursively find a list/tuple of plaintext numeric backup codes."""
        found = []
        if isinstance(value, dict):
            for nested in value.values():
                found.extend(self._find_backup_code_lists(nested))
            return found

        if isinstance(value, (list, tuple)):
            if value and all(self._looks_like_backup_code(item) for item in value):
                return [list(value)]
            for nested in value:
                found.extend(self._find_backup_code_lists(nested))
        return found

    def _extract_backup_codes(self, response):
        sources = [
            getattr(response, "context_data", {}),
            self.rendered_contexts,
            dict(self.client.session.items()),
        ]
        try:
            response_context = getattr(response, "context", None)
            if response_context is not None:
                sources.append(response_context)
        except Exception:
            # response.context may be unavailable when templates are bypassed.
            pass

        code_lists = []
        for source in sources:
            code_lists.extend(self._find_backup_code_lists(source))

        if not code_lists:
            self.fail(
                "The BackupCodeSetupView response/session did not expose the "
                "plaintext backup-code list. Update _extract_backup_codes() to "
                "match the current context/session key used by user_app."
            )

        # Prefer the longest group, which should be the initial one-time code set.
        return max(code_lists, key=len)

    # ------------------------------------------------------------------
    # Full lifecycle
    # ------------------------------------------------------------------

    def test_complete_application_lifecycle_from_registration_to_recovery(self):
        User = get_user_model()

        # 1. Register a brand-new user through the real registration endpoint.
        register_url = self._url_for_view("RegisterView")
        response = self.client.post(register_url, self._registration_payload())
        self.assertEqual(
            response.status_code,
            302,
            "Valid registration should redirect instead of returning the form.",
        )

        self.user = User.objects.get(username=self.username)
        self.assertTrue(self.user.check_password(self.initial_password))
        self.assertEqual(
            str(self.user.pk),
            str(self.client.session.get("_auth_user_id")),
            "The registration flow is expected to sign the user in.",
        )

        # 2. Set up and confirm the one-time backup codes.
        backup_setup_url = self._url_for_view("BackupCodeSetupView", user=self.user)
        setup_response = self.client.get(backup_setup_url)
        self.assertEqual(setup_response.status_code, 200)

        self.backup_codes = self._extract_backup_codes(setup_response)
        self.assertEqual(
            len(self.backup_codes),
            10,
            "The initial backup-code setup is expected to issue ten one-time codes.",
        )
        self.assertTrue(all(self._looks_like_backup_code(code) for code in self.backup_codes))

        # The endpoint accepts the confirmation via POST. Unused aliases are
        # ignored by Django forms; the project's actual expected field is used
        # if it matches one of these common names.
        confirmation_payload = {
            "confirm_saved": "on",
            "codes_saved": "on",
            "saved_codes": "on",
            "saved": "on",
            "confirm": "on",
            "acknowledged": "on",
            "action": "confirm",
        }
        confirm_response = self.client.post(backup_setup_url, confirmation_payload)
        self.assertIn(confirm_response.status_code, (200, 302))
        self.assertEqual(BackupCode.objects.filter(user=self.user).count(), 10)

        # 3. Create two Vaults through VaultCreateView and confirm persistence.
        vault_create_url = self._url_for_view("VaultCreateView", user=self.user)

        response = self.client.post(
            vault_create_url,
            self._vault_payload("Integration Personal"),
        )
        self.assertEqual(response.status_code, 302)
        self.personal_vault = Vault.objects.get(
            user=self.user,
            slug="integration-personal",
        )

        response = self.client.post(
            vault_create_url,
            self._vault_payload("Integration Work"),
        )
        self.assertEqual(response.status_code, 302)
        self.work_vault = Vault.objects.get(
            user=self.user,
            slug="integration-work",
        )
        self.assertNotEqual(self.personal_vault.pk, self.work_vault.pk)

        # 4. Update a Vault and ensure the URL slug remains stable on rename.
        original_personal_slug = self.personal_vault.slug
        vault_update_url = self._url_for_view(
            "VaultUpdateView",
            user=self.user,
            vault=self.personal_vault,
        )
        response = self.client.post(
            vault_update_url,
            self._vault_payload("Integration Personal Renamed"),
        )
        self.assertEqual(response.status_code, 302)
        self.personal_vault.refresh_from_db()
        self.assertEqual(self.personal_vault.name, "Integration personal renamed")
        self.assertEqual(self.personal_vault.slug, original_personal_slug)

        # 5. Create and update a Category through HTTP views.
        category_create_url = self._url_for_view("CategoryCreateView", user=self.user)
        response = self.client.post(
            category_create_url,
            self._category_payload("Social Integration"),
        )
        self.assertEqual(response.status_code, 302)
        self.category = Category.objects.get(
            user=self.user,
            name="Social Integration",
        )

        category_update_url = self._url_for_view(
            "CategoryUpdateView",
            user=self.user,
            category=self.category,
        )
        response = self.client.post(
            category_update_url,
            self._category_payload("Social Updated"),
        )
        self.assertEqual(response.status_code, 302)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Social Updated")

        # 6. Create a Credential through the real form, view, service, and DB.
        # Encryption is isolated here so the journey does not depend on a
        # developer machine's environment-specific Fernet key. Dedicated crypto
        # tests should cover the actual encryption implementation separately.
        with patch(
            "credential_app.services.credential_service.EncryptionService.encrypt",
            side_effect=lambda value: f"test-ciphertext::{value}",
        ) as encrypt_mock:
            response = self.client.post(
                self._url_for_view(
                    "CredentialCreateView",
                    user=self.user,
                    vault=self.personal_vault,
                ),
                self._credential_payload(),
            )

            self.assertEqual(response.status_code, 302)
            self.credential = Credential.objects.get(
                vault=self.personal_vault,
                service_name="GitHub",
            )
            self.assertEqual(
                self.credential.password_ciphertext,
                f"test-ciphertext::{self.credential_password}",
            )
            self.assertNotEqual(
                self.credential.password_ciphertext,
                self.credential_password,
                "The plaintext Credential password must not be stored as ciphertext.",
            )
            encrypt_mock.assert_called_once_with(self.credential_password)

            # 7. Update Credential metadata without rotating its password.
            previous_ciphertext = self.credential.password_ciphertext
            update_payload = {
                "service_name": "GitHub Business",
                "service_url": "https://github.com/enterprise",
                "login_username": "e2e-updated-login",
                "login_email": "e2e-updated@example.test",
                "category": str(self.category.pk),
                "category_id": str(self.category.pk),
                "notes": "Updated by end-to-end test.",
                # "No" is_favorite checkbox: this intentionally means false.
            }
            response = self.client.post(
                self._url_for_view(
                    "CredentialUpdateView",
                    user=self.user,
                    vault=self.personal_vault,
                    credential=self.credential,
                ),
                update_payload,
            )
            self.assertEqual(response.status_code, 302)
            self.credential.refresh_from_db()
            self.assertEqual(self.credential.service_name, "GitHub Business")
            self.assertEqual(self.credential.login_username, "e2e-updated-login")
            self.assertEqual(self.credential.category_id, self.category.pk)
            self.assertEqual(self.credential.password_ciphertext, previous_ciphertext)

            # 8. List/search and detail routes work without rendering HTML.
            list_url = self._url_for_view(
                "CredentialListView",
                user=self.user,
                vault=self.personal_vault,
            )
            response = self.client.get(list_url, {"q": "GitHub Business"})
            self.assertEqual(response.status_code, 200)
            list_context = getattr(response, "context_data", {}) or {}
            credentials_in_context = list_context.get("credentials")
            if credentials_in_context is not None:
                self.assertIn(self.credential, credentials_in_context)

            detail_url = self._url_for_view(
                "CredentialDetailView",
                user=self.user,
                vault=self.personal_vault,
                credential=self.credential,
            )
            with patch(
                "credential_app.views.EncryptionService.decrypt",
                return_value=self.credential_password,
            ) as decrypt_mock:
                response = self.client.get(detail_url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response.headers.get("Cache-Control", ""))
            decrypt_mock.assert_called_once_with(previous_ciphertext)

            # 9. Rotate the Credential password and verify history creation.
            with patch(
                "credential_app.services.credential_service.EncryptionService.encrypt",
                side_effect=lambda value: f"test-ciphertext::{value}",
            ):
                response = self.client.post(
                    self._url_for_view(
                        "CredentialRotatePasswordView",
                        user=self.user,
                        vault=self.personal_vault,
                        credential=self.credential,
                    ),
                    {
                        "new_password": self.rotated_password,
                        "confirm_new_password": self.rotated_password,
                    },
                )
            self.assertEqual(response.status_code, 302)
            self.credential.refresh_from_db()
            self.assertEqual(
                self.credential.password_ciphertext,
                f"test-ciphertext::{self.rotated_password}",
            )
            self.assertEqual(
                CredentialHistory.objects.filter(credential=self.credential).count(),
                1,
            )

            history = CredentialHistory.objects.get(credential=self.credential)
            self.assertEqual(history.old_password_ciphertext, previous_ciphertext)
            self.assertEqual(
                history.new_password_ciphertext,
                f"test-ciphertext::{self.rotated_password}",
            )

            # 10. Toggle favorite using the POST-only endpoint.
            response = self.client.post(
                self._url_for_view(
                    "CredentialToggleFavoriteView",
                    user=self.user,
                    vault=self.personal_vault,
                    credential=self.credential,
                )
            )
            self.assertEqual(response.status_code, 302)
            self.credential.refresh_from_db()
            self.assertTrue(self.credential.is_favorite)

            # 11. Move Credential to another user-owned Vault.
            response = self.client.post(
                self._url_for_view(
                    "CredentialMoveToVaultView",
                    user=self.user,
                    vault=self.personal_vault,
                    credential=self.credential,
                ),
                {
                    "target_vault": str(self.work_vault.pk),
                    "vault": str(self.work_vault.pk),
                },
            )
            self.assertEqual(response.status_code, 302)
            self.credential.refresh_from_db()
            self.assertEqual(self.credential.vault_id, self.work_vault.pk)

            # 12. Delete the Credential via HTTP; its history should cascade.
            response = self.client.post(
                self._url_for_view(
                    "CredentialDeleteView",
                    user=self.user,
                    vault=self.work_vault,
                    credential=self.credential,
                )
            )
            self.assertEqual(response.status_code, 302)
            self.assertFalse(Credential.objects.filter(pk=self.credential.pk).exists())
            self.assertFalse(
                CredentialHistory.objects.filter(credential_id=self.credential.pk).exists()
            )

        # 13. Delete Category and both non-default Vaults through HTTP.
        response = self.client.post(
            self._url_for_view(
                "CategoryDeleteView",
                user=self.user,
                category=self.category,
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=self.category.pk).exists())

        response = self.client.post(
            self._url_for_view(
                "VaultDeleteView",
                user=self.user,
                vault=self.work_vault,
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Vault.objects.filter(pk=self.work_vault.pk).exists())

        response = self.client.post(
            self._url_for_view(
                "VaultDeleteView",
                user=self.user,
                vault=self.personal_vault,
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Vault.objects.filter(pk=self.personal_vault.pk).exists())

        # 14. Log out, then verify the normal login flow with the original password.
        logout_url = self._url_for_view("LogoutView", user=self.user)
        response = self.client.post(logout_url)
        self.assertIn(response.status_code, (200, 302))
        self.assertFalse(self.client.session.get("_auth_user_id"))

        login_url = self._url_for_view("LoginView", user=self.user)
        response = self.client.post(
            login_url,
            {
                "username": self.username,
                "password": self.initial_password,
                "master_password": self.initial_password,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            str(self.user.pk),
            str(self.client.session.get("_auth_user_id")),
        )

        # 15. Log out again, start recovery with one backup code, reset the
        # Master Password, and sign in with the replacement password.
        self.client.post(logout_url)
        recovery_view_name = self._find_recovery_view_name()
        self.assertIsNotNone(
            recovery_view_name,
            "Could not locate a recovery endpoint in the active URLconf. "
            "Update _find_recovery_view_name() to match the current view class name.",
        )
        recovery_url = self._url_for_view(
            recovery_view_name,
            user=self.user,
            extra={
                "code": self.backup_codes[0],
                "backup_code": self.backup_codes[0],
                "recovery_code": self.backup_codes[0],
            },
        )
        recovery_response = self.client.post(
            recovery_url,
            {
                "username": self.username,
                "backup_code": self.backup_codes[0],
                "recovery_code": self.backup_codes[0],
                "code": self.backup_codes[0],
            },
        )
        self.assertIn(recovery_response.status_code, (200, 302))

        reset_url = self._url_for_view("ResetMasterPasswordView", user=self.user)
        reset_response = self.client.post(
            reset_url,
            {
                "password": self.replacement_password,
                "confirm_password": self.replacement_password,
                "password_confirm": self.replacement_password,
                "password_confirmation": self.replacement_password,
                "new_password": self.replacement_password,
                "confirm_new_password": self.replacement_password,
                "master_password": self.replacement_password,
                "confirm_master_password": self.replacement_password,
                "password1": self.replacement_password,
                "password2": self.replacement_password,
            },
        )
        self.assertIn(reset_response.status_code, (200, 302))
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password(self.replacement_password),
            "The recovery flow should replace the stored Master Password.",
        )
        self.assertFalse(self.user.check_password(self.initial_password))

        # After recovery, the user should be able to authenticate normally.
        self.client.post(logout_url)
        response = self.client.post(
            login_url,
            {
                "username": self.username,
                "password": self.replacement_password,
                "master_password": self.replacement_password,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            str(self.user.pk),
            str(self.client.session.get("_auth_user_id")),
        )
