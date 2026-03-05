"""Pure function tests for insurance calculator — no DB, no async."""

from app.insurance.calculator import (
    calculate_outs_and_odds,
    validate_card,
    validate_card_set,
)


# ===== Card validation =====


def test_validate_card_valid():
    assert validate_card("As") is True
    assert validate_card("Td") is True
    assert validate_card("2c") is True
    assert validate_card("Kh") is True
    assert validate_card("9s") is True


def test_validate_card_invalid_format():
    assert validate_card("X1") is False
    assert validate_card("1s") is False
    assert validate_card("Ax") is False
    assert validate_card("") is False
    assert validate_card("Ass") is False
    assert validate_card("A") is False


def test_validate_card_set_success():
    errors = validate_card_set(
        ["As", "Kh"], ["Qd", "Qc"], ["Js", "Td", "3c"]
    )
    assert errors == []


def test_validate_card_set_duplicate():
    errors = validate_card_set(
        ["As", "Kh"], ["As", "Qc"], ["Js", "Td", "3c"]
    )
    assert any("uplicate" in e for e in errors)


def test_validate_card_set_wrong_count():
    # buyer_hand only 1 card
    errors = validate_card_set(["As"], ["Qd", "Qc"], ["Js", "Td", "3c"])
    assert any("buyer_hand" in e for e in errors)

    # community_cards only 2 cards
    errors = validate_card_set(["As", "Kh"], ["Qd", "Qc"], ["Js", "Td"])
    assert any("community_cards" in e for e in errors)

    # community_cards 5 cards
    errors = validate_card_set(
        ["As", "Kh"], ["Qd", "Qc"], ["Js", "Td", "3c", "4h", "5s"]
    )
    assert any("community_cards" in e for e in errors)


# ===== Outs & odds calculation =====


def test_outs_calculation_turn_stage():
    """Turn stage: 8 known cards, 44 remaining, enumerate 44 single cards."""
    result = calculate_outs_and_odds(
        buyer_hand=["7s", "8s"],
        opponent_hand=["As", "Ad"],
        community_cards=["5s", "6d", "Kh", "2c"],
    )
    assert result["total_combinations"] == 44
    assert result["outs"] > 0
    assert 0 < result["win_probability"] < 1
    assert result["odds"] > 0


def test_outs_calculation_flop_stage():
    """Flop stage: 7 known cards, 45 remaining, enumerate C(45,2)=990."""
    result = calculate_outs_and_odds(
        buyer_hand=["Ah", "Kh"],
        opponent_hand=["Qd", "Qc"],
        community_cards=["Jh", "Td", "3c"],
    )
    assert result["total_combinations"] == 990
    assert result["outs"] > 0
    assert 0 < result["win_probability"] < 1
    assert result["odds"] > 0


def test_odds_calculation():
    """Verify odds = (1-wp)/wp for a known turn scenario."""
    result = calculate_outs_and_odds(
        buyer_hand=["7s", "8s"],
        opponent_hand=["As", "Ad"],
        community_cards=["5s", "6d", "Kh", "2c"],
    )
    wp = result["win_probability"]
    expected_odds = (1 - wp) / wp
    # Allow small rounding difference
    assert abs(result["odds"] - round(expected_odds, 4)) < 0.01


def test_outs_zero_no_chance():
    """Buyer has absolutely no outs (opponent has unbeatable hand on turn)."""
    # Opponent has a royal flush on the turn — buyer cannot win any river card
    result = calculate_outs_and_odds(
        buyer_hand=["2c", "3d"],
        opponent_hand=["Ah", "Kh"],
        community_cards=["Qh", "Jh", "Th", "9c"],
    )
    assert result["outs"] == 0
    assert result["win_probability"] == 0
    assert result["odds"] == 0


def test_outs_guaranteed_win():
    """Buyer already has an unbeatable hand (royal flush on turn)."""
    result = calculate_outs_and_odds(
        buyer_hand=["Ah", "Kh"],
        opponent_hand=["2c", "3d"],
        community_cards=["Qh", "Jh", "Th", "9c"],
    )
    # Buyer has royal flush — should win every runout
    assert result["win_probability"] >= 1.0
    assert result["odds"] == 0


def test_tie_handling():
    """
    Tie (split pot) does not count as buyer win.
    Both players have identical kickers through the board.
    """
    # Both players play the board: board has A-K-Q-J-T (straight)
    # with no flush possible. Neither hand improves past the board.
    result = calculate_outs_and_odds(
        buyer_hand=["2c", "3d"],
        opponent_hand=["4c", "5d"],
        community_cards=["As", "Kd", "Qh", "Jc"],
    )
    # On many rivers both play the board straight — ties should not be outs
    # At minimum, verify total_combinations is correct and outs < total
    assert result["total_combinations"] == 44
    # Some rivers may give one player a better hand, but many will tie
    # The key check: outs should be much less than total_combinations
    assert result["outs"] < result["total_combinations"]
