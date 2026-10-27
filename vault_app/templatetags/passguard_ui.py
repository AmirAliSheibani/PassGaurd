"""Small, validation-focused template filters for PassGuard UI components."""

import re

from django import template

register = template.Library()
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_DEFAULT_COLOR = "#67E8F9"


@register.filter
def hex_color(value):
    """Return a valid six-digit CSS hex color or the UI accent fallback.

    Model values can be changed from admin or scripts, so template output must
    not rely solely on form validation before embedding a value in CSS.
    """
    if not isinstance(value, str) or not _HEX_COLOR.fullmatch(value):
        return _DEFAULT_COLOR
    return value.upper()
