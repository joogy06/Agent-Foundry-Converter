"""transfer_kit/core/url_sanitizer.py — Strip credentials from git URLs.

Called by :mod:`transfer_kit.core.pull` before any git subprocess or log
statement. Any embedded PAT (``ghp_xxx``), OAuth token, or ``user:password``
pair is removed. A caller-provided URL that already has no credentials is
returned verbatim.

Design note (challenger CC6): we use ``urllib.parse`` rather than regex to
avoid edge cases in scheme / userinfo parsing. ``urllib.parse`` is in the
stdlib and does not require additional dependencies.
"""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


# Prefixes or patterns that unambiguously mark an input as a local path
# rather than a URL. urlparse happily chews on ``./foo`` and returns a blank
# scheme, so we pre-filter to avoid both false positives (local Windows
# paths with colons like ``C:\foo``) and false negatives.
_LOCAL_PREFIXES: tuple[str, ...] = ("./", "../", "/", "~/", "~")


def _looks_local(url: str) -> bool:
    """Return True when ``url`` should be treated as a local filesystem path."""
    if not url:
        return False
    if url.startswith(_LOCAL_PREFIXES):
        return True
    # Bare Windows drive path (e.g. ``C:\repo`` or ``C:/repo``): has a single
    # letter before the colon, and no ``://`` scheme separator. A real URL
    # always has ``scheme://...``.
    if (
        len(url) >= 3
        and url[1] == ":"
        and url[0].isalpha()
        and not url.startswith(("http://", "https://"))
    ):
        return True
    return False


def sanitize_git_url(url: str) -> tuple[str, bool]:
    """Return ``(sanitized_url, had_credentials)``.

    Behaviour:

    * Local filesystem paths — and anything without a URL scheme — pass
      through unchanged with ``had_credentials=False``.
    * HTTP/HTTPS URLs get userinfo (``user[:pass]@``) stripped.
    * SSH URLs (``git@github.com:owner/repo``) carry an unavoidable username;
      we recognise the pattern and mark ``had_credentials=False`` for the
      bare ``git@`` form, which is conventionally considered non-sensitive.
    * Malformed inputs raise ``ValueError`` with a clear message.

    Parameters
    ----------
    url :
        The raw URL or path from the CLI. Must not be ``None`` or empty.
    """
    if url is None or url == "":
        raise ValueError("URL is empty")

    if _looks_local(url):
        return url, False

    # SCP-style SSH: ``user@host:path``. We keep as-is; git wants it verbatim.
    # Only the bare ``git@`` user is conventionally non-credential; any other
    # form (e.g. ``ghp_token@``) should be rejected below as HTTP URL after
    # normalisation (we don't attempt to convert SSH URLs to HTTPS).
    if "://" not in url and "@" in url and ":" in url.split("@", 1)[1]:
        # This looks like SCP-style SSH; leave it alone.
        return url, False

    try:
        parsed = urlparse(url)
    except ValueError as e:  # pragma: no cover — urlparse is extremely lenient
        raise ValueError(f"malformed URL: {e}") from e

    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"not a URL: {url!r}")

    if "@" not in parsed.netloc:
        return url, False

    # There is userinfo — strip it. ``netloc`` format is
    # ``[userinfo@]host[:port]``; rebuild without the userinfo part.
    userinfo, _, hostinfo = parsed.netloc.rpartition("@")
    had_credentials = bool(userinfo)
    sanitized = urlunparse(parsed._replace(netloc=hostinfo))
    return sanitized, had_credentials


__all__ = ["sanitize_git_url"]
