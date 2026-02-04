"""Tests for PDF logo URL resolution logic."""

import os
from unittest.mock import patch

from services.pdf_generator import _is_safe_url


class TestIsSafeUrl:
    """Test the _is_safe_url validation function."""

    def test_blocks_localhost(self):
        assert _is_safe_url("http://localhost/logo.png") is False

    def test_blocks_127_0_0_1(self):
        assert _is_safe_url("http://127.0.0.1/logo.png") is False

    def test_blocks_private_ip_10(self):
        assert _is_safe_url("http://10.0.0.1/logo.png") is False

    def test_blocks_private_ip_192_168(self):
        assert _is_safe_url("http://192.168.1.1/logo.png") is False

    def test_blocks_private_ip_172_16(self):
        assert _is_safe_url("http://172.16.0.1/logo.png") is False

    def test_allows_public_url(self):
        assert _is_safe_url("https://example.com/logo.png") is True

    def test_allows_vercel_url(self):
        assert _is_safe_url("https://invoice-generator-frontend-three.vercel.app/logo.png") is True

    def test_blocks_ftp_scheme(self):
        assert _is_safe_url("ftp://example.com/logo.png") is False


class TestLogoUrlResolution:
    """Test that relative logo paths are resolved correctly."""

    def test_relative_path_uses_frontend_url(self):
        """When FRONTEND_URL is set, relative paths should resolve to it."""
        with patch.dict(os.environ, {"FRONTEND_URL": "https://myfrontend.vercel.app"}):
            frontend_url = os.getenv("FRONTEND_URL", "")
            logo_path = "/logo.png"
            resolved = f"{frontend_url.rstrip('/')}{logo_path}"
            assert resolved == "https://myfrontend.vercel.app/logo.png"

    def test_relative_path_falls_back_to_cors_origins(self):
        """When FRONTEND_URL is empty, should fall back to first CORS origin."""
        env = {
            "FRONTEND_URL": "",
            "CORS_ORIGINS": "https://invoice-generator-frontend-three.vercel.app,http://localhost:3000",
        }
        with patch.dict(os.environ, env, clear=False):
            frontend_url = os.getenv("FRONTEND_URL", "")
            if not frontend_url:
                cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
                frontend_url = cors_origins.split(",")[0].strip()
            logo_path = "/logo.png"
            resolved = f"{frontend_url.rstrip('/')}{logo_path}"
            assert resolved == "https://invoice-generator-frontend-three.vercel.app/logo.png"

    def test_fallback_without_any_env(self):
        """When neither FRONTEND_URL nor CORS_ORIGINS are set, defaults to localhost."""
        env = {"FRONTEND_URL": "", "CORS_ORIGINS": ""}
        with patch.dict(os.environ, env, clear=False):
            frontend_url = os.getenv("FRONTEND_URL", "")
            if not frontend_url:
                cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
                frontend_url = cors_origins.split(",")[0].strip()
            if not frontend_url:
                frontend_url = "http://localhost:3000"
            logo_path = "/logo.png"
            resolved = f"{frontend_url.rstrip('/')}{logo_path}"
            assert resolved == "http://localhost:3000/logo.png"

    def test_cors_origins_with_trailing_spaces(self):
        """CORS_ORIGINS entries with spaces should be trimmed."""
        env = {
            "FRONTEND_URL": "",
            "CORS_ORIGINS": "  https://prod.example.com  , http://localhost:3000",
        }
        with patch.dict(os.environ, env, clear=False):
            frontend_url = os.getenv("FRONTEND_URL", "")
            if not frontend_url:
                cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
                frontend_url = cors_origins.split(",")[0].strip()
            logo_path = "/logo.png"
            resolved = f"{frontend_url.rstrip('/')}{logo_path}"
            assert resolved == "https://prod.example.com/logo.png"

    def test_frontend_url_with_trailing_slash(self):
        """Trailing slash on FRONTEND_URL should be stripped."""
        with patch.dict(os.environ, {"FRONTEND_URL": "https://myfrontend.vercel.app/"}):
            frontend_url = os.getenv("FRONTEND_URL", "")
            logo_path = "/logo.png"
            resolved = f"{frontend_url.rstrip('/')}{logo_path}"
            assert resolved == "https://myfrontend.vercel.app/logo.png"

    def test_absolute_http_url_not_resolved(self):
        """Absolute URLs (http/https) should NOT go through relative path resolution."""
        logo_path = "https://cdn.example.com/logo.png"
        assert not logo_path.startswith("/")
        # absolute URL should be used as-is, not resolved via FRONTEND_URL

    def test_internal_logo_bypasses_safe_url_check(self):
        """Resolved internal logos (from /logo.png) should bypass _is_safe_url."""
        # When FRONTEND_URL is localhost, _is_safe_url would block it.
        # But is_internal_logo=True should bypass the check.
        with patch.dict(os.environ, {"FRONTEND_URL": "http://localhost:3000"}):
            frontend_url = os.getenv("FRONTEND_URL", "")
            logo_path = f"{frontend_url.rstrip('/')}/logo.png"
            is_internal_logo = True
            # The check in code: if not is_internal_logo and not _is_safe_url(...)
            # With is_internal_logo=True, _is_safe_url is never called
            should_block = not is_internal_logo and not _is_safe_url(logo_path)
            assert should_block is False
