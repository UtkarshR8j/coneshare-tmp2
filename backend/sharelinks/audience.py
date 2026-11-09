"""Audience allowlist matching for share links.

An allowlist entry is either an exact email address or a wildcard pattern such as
``*@acme.com`` or ``utkarsh@*.acme.com``. Matching is case-insensitive. The accepted
character set is deliberately narrow so ``?`` and ``[]`` cannot act as surprise
wildcards inside fnmatch.
"""
import re
from fnmatch import fnmatchcase

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

ENTRY_RE = re.compile(r'^[a-z0-9.+_%*-]+@[a-z0-9.*-]+$')
MAX_ENTRIES = 500
INVALID_ENTRY_MESSAGE = 'Enter an email address or a pattern like *@example.com.'


def clean_entry(raw):
    """Lowercase and validate one allowlist entry. Raises ValidationError."""
    value = (raw or '').strip().lower()
    if not value or not ENTRY_RE.match(value):
        raise ValidationError(INVALID_ENTRY_MESSAGE)
    if value in ('@', '*@', '@*'):
        raise ValidationError(INVALID_ENTRY_MESSAGE)
    if '*' not in value:
        try:
            validate_email(value)
        except ValidationError:
            raise ValidationError('Enter a valid email address.')
    return value


def normalize_entries(values):
    """Clean, lowercase and de-duplicate an allowlist, preserving order."""
    cleaned = []
    for raw in values or []:
        value = clean_entry(raw)
        if value not in cleaned:
            cleaned.append(value)
    if len(cleaned) > MAX_ENTRIES:
        raise ValidationError(f'Add at most {MAX_ENTRIES} entries.')
    return cleaned


def email_matches(email, patterns):
    """True when a viewer email matches at least one allowlist entry."""
    email = (email or '').strip().lower()
    if not email:
        return False
    return any(fnmatchcase(email, p) for p in patterns if isinstance(p, str) and p)
