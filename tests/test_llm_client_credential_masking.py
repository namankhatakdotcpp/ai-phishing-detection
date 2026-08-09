"""Tests describe_env_key() never leaks the full credential value — only
uses fake, obviously-not-real test values, never a real key.
"""

from phishshield.data.llm_client import describe_env_key


def test_describe_env_key_masks_a_long_fake_value(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "FAKE-TEST-VALUE-1234567890-not-a-real-key")
    result = describe_env_key("gemini")
    assert "is set" in result
    assert "FAKE-TEST-VALUE-1234567890-not-a-real-key" not in result
    assert "FAKE-T" in result  # prefix shown
    assert "-key" in result  # suffix shown


def test_describe_env_key_reports_absence_without_guessing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    result = describe_env_key("gemini")
    assert "no credentials found" in result


def test_describe_env_key_falls_back_to_second_env_var(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "FAKE-OTHER-VALUE-abcdef")
    result = describe_env_key("gemini")
    assert "GOOGLE_API_KEY is set" in result
    assert "FAKE-OTHER-VALUE-abcdef" not in result


def test_describe_env_key_short_value_is_fully_masked(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "short")
    result = describe_env_key("anthropic")
    assert "short" not in result
    assert "<set>" in result
