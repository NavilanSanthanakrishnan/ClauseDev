from __future__ import annotations

import json
import tempfile
import unittest
from base64 import urlsafe_b64encode
from pathlib import Path
from unittest.mock import patch

from step1.services.codex_auth import resolve_codex_runtime_credentials


def _jwt(payload: dict[str, object]) -> str:
    header = urlsafe_b64encode(json.dumps({"alg": "none"}).encode("utf-8")).decode("ascii").rstrip("=")
    body = urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    return f"{header}.{body}.sig"


class CodexAuthTests(unittest.TestCase):
    def test_resolves_account_id_from_access_token_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_path = Path(tmpdir) / "auth.json"
            auth_path.write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "tokens": {
                            "access_token": _jwt(
                                {
                                    "exp": 4_102_444_800,
                                    "https://api.openai.com/auth": {
                                        "chatgpt_account_id": "acct-from-claim",
                                    },
                                }
                            ),
                            "refresh_token": "refresh-token",
                        },
                    }
                ),
                encoding="utf-8",
            )

            creds = resolve_codex_runtime_credentials(codex_home=tmpdir, refresh_if_expiring=False)

            self.assertEqual(creds["account_id"], "acct-from-claim")

    def test_does_not_require_refresh_token_until_refresh_is_needed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_path = Path(tmpdir) / "auth.json"
            auth_path.write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "tokens": {
                            "access_token": _jwt(
                                {
                                    "exp": 4_102_444_800,
                                    "https://api.openai.com/auth": {
                                        "chatgpt_account_id": "acct-live",
                                    },
                                }
                            ),
                        },
                    }
                ),
                encoding="utf-8",
            )

            creds = resolve_codex_runtime_credentials(codex_home=tmpdir, refresh_if_expiring=True)

            self.assertEqual(creds["account_id"], "acct-live")
            self.assertEqual(creds["refresh_token"], "")

    def test_refresh_persists_last_refresh_and_account_id_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_path = Path(tmpdir) / "auth.json"
            auth_path.write_text(
                json.dumps(
                    {
                        "auth_mode": "chatgpt",
                        "tokens": {
                            "access_token": _jwt({"exp": 1}),
                            "refresh_token": "refresh-token",
                        },
                    }
                ),
                encoding="utf-8",
            )

            refreshed_access_token = _jwt(
                {
                    "exp": 4_102_444_800,
                    "https://api.openai.com/auth": {"chatgpt_account_id": "acct-refreshed"},
                }
            )
            with patch("step1.services.codex_auth.httpx.Client") as mock_client_cls:
                mock_client = mock_client_cls.return_value.__enter__.return_value
                mock_client.post.return_value.status_code = 200
                mock_client.post.return_value.json.return_value = {
                    "access_token": refreshed_access_token,
                    "refresh_token": "new-refresh-token",
                }

                creds = resolve_codex_runtime_credentials(codex_home=tmpdir, refresh_if_expiring=True)

            payload = json.loads(auth_path.read_text(encoding="utf-8"))
            self.assertEqual(creds["account_id"], "acct-refreshed")
            self.assertEqual(payload["tokens"]["account_id"], "acct-refreshed")
            self.assertEqual(payload["tokens"]["refresh_token"], "new-refresh-token")
            self.assertIn("last_refresh", payload)


if __name__ == "__main__":
    unittest.main()
