# PassGuard template architecture

## Structure

- `base.html` is the only document shell. It loads the shared CSS/JS, renders authenticated navigation, messages, the content block, and the footer.
- `partials/` contains small reusable UI components: form fields and errors, page headings, vault/category/credential summaries, password value, messages, confirmation actions, icons, and the one-time backup-code grid.
- Each Django app has a namespace folder (`core/`, `user_app/`, `vault_app/`, `credential_app/`) for its page templates. Page templates extend `base.html` and use `partials/` rather than duplicate layouts.

## Page templates

### `core`
- `core/home.html` — public landing page when anonymous, dashboard/workspace when authenticated.

### `user_app`
- `user_app/login.html`
- `user_app/register.html`
- `user_app/backup_code_setup.html`
- `user_app/backup_code_recovery.html`
- `user_app/reset_master_password.html`
- `user_app/regenerate_backup_codes.html`

### `vault_app`
- `vault_app/vault_list.html`
- `vault_app/vault_detail.html`
- `vault_app/vault_form.html` — create/update shared form.
- `vault_app/vault_confirm_delete.html`
- `vault_app/category_list.html`
- `vault_app/category_form.html` — create/update shared form.
- `vault_app/category_confirm_delete.html`

### `credential_app`
- `credential_app/credential_list.html`
- `credential_app/credential_form.html` — create/update shared form.
- `credential_app/credential_detail.html`
- `credential_app/credential_confirm_delete.html`
- `credential_app/credential_rotate_password.html`
- `credential_app/credential_move_to_vault.html`

## Integration notes

1. The uploaded project already configures `BASE_DIR / "templates"` in `TEMPLATES[0]["DIRS"]`, enables `APP_DIRS`, and registers `vault_app.context_processors.navigation_context`. Preserve those settings.
2. The uploaded project already contains the shared `static/passguard/` CSS and JS assets and `vault_app/templatetags/passguard_ui.py`.
3. The package includes a small updated `core/views.py` to render `core/home.html` and provide real dashboard counts.
4. The package's updated `vault_app/views.py` adds credential counts for vault cards, supplies vault detail content through `CredentialSelector`, and includes missing `vault`/`category` objects on edit form GET requests.
5. The templates use the current named URLs from the uploaded URLconfs. No URL names are added or renamed.

## Important password-display note

The current `CredentialDetailView` decrypts the credential password and includes it in the server-rendered response. The reusable password display masks it visually, but it is not a server-side security boundary. The detail template states this explicitly. To avoid sending plaintext until a user requests reveal, a backend endpoint and a different disclosure flow are required.
