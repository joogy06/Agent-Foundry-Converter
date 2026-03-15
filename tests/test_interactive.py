"""Tests for the interactive module."""

from transfer_kit.interactive import MENU_CHOICES


def test_menu_choices_defined():
    assert isinstance(MENU_CHOICES, list)
    assert len(MENU_CHOICES) >= 7


def test_menu_choices_has_exit():
    assert "Exit" in MENU_CHOICES


def test_export_item_choices_defined():
    from transfer_kit.interactive import EXPORT_ITEM_CHOICES

    assert isinstance(EXPORT_ITEM_CHOICES, list)
    assert "all" in EXPORT_ITEM_CHOICES


def test_convert_target_choices_defined():
    from transfer_kit.interactive import CONVERT_TARGET_CHOICES

    assert isinstance(CONVERT_TARGET_CHOICES, list)
    assert "copilot" in CONVERT_TARGET_CHOICES
    assert "gemini" in CONVERT_TARGET_CHOICES
    assert "windsurf" in CONVERT_TARGET_CHOICES
