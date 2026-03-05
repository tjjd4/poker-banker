"""
Poker insurance calculator — pure functions, no DB, no async.

Card format: "{Rank}{Suit}" e.g. "As" = Ace of spades, "Td" = Ten of diamonds.
"""

from itertools import combinations

from treys import Card, Evaluator

VALID_RANKS = set("23456789TJQKA")
VALID_SUITS = set("shdc")
FULL_DECK = [r + s for r in "23456789TJQKA" for s in "shdc"]

# Module-level evaluator singleton (lookup tables built once)
_evaluator = Evaluator()


def validate_card(card: str) -> bool:
    """Validate a single card string. Must be exactly 2 chars: rank + suit."""
    if not isinstance(card, str) or len(card) != 2:
        return False
    return card[0] in VALID_RANKS and card[1] in VALID_SUITS


def validate_card_set(
    buyer_hand: list[str],
    opponent_hand: list[str],
    community_cards: list[str],
) -> list[str]:
    """
    Validate the complete card set for an insurance calculation.
    Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []

    if len(buyer_hand) != 2:
        errors.append("buyer_hand must have exactly 2 cards")
    if len(opponent_hand) != 2:
        errors.append("opponent_hand must have exactly 2 cards")
    if len(community_cards) not in (3, 4):
        errors.append("community_cards must have 3 or 4 cards")

    all_cards = buyer_hand + opponent_hand + community_cards
    for c in all_cards:
        if not validate_card(c):
            errors.append(f"Invalid card: {c}")

    if len(all_cards) != len(set(all_cards)):
        errors.append("Duplicate cards detected")

    return errors


def calculate_outs_and_odds(
    buyer_hand: list[str],
    opponent_hand: list[str],
    community_cards: list[str],
) -> dict:
    """
    Calculate All-in insurance outs count and odds using exact enumeration.

    The "buyer" is typically the player who is behind (buying insurance).
    Outs = number of unique remaining cards that appear in at least one
    combination where the buyer wins.

    Returns:
        {
            "outs": int,
            "total_combinations": int,
            "win_probability": float,
            "odds": float,
        }
    """
    # Convert to treys integer format
    buyer_ints = [Card.new(c) for c in buyer_hand]
    opponent_ints = [Card.new(c) for c in opponent_hand]
    board_ints = [Card.new(c) for c in community_cards]

    # Remaining deck
    known = set(buyer_ints + opponent_ints + board_ints)
    full_deck_ints = [Card.new(c) for c in FULL_DECK]
    remaining = [c for c in full_deck_ints if c not in known]

    # Cards to come: flop(3) → 2 more, turn(4) → 1 more
    cards_to_come = 5 - len(community_cards)

    buyer_wins = 0
    out_cards: set[int] = set()
    total_combinations = 0

    for combo in combinations(remaining, cards_to_come):
        total_combinations += 1
        full_board = board_ints + list(combo)
        buyer_rank = _evaluator.evaluate(buyer_ints, full_board)
        opponent_rank = _evaluator.evaluate(opponent_ints, full_board)
        # Lower rank = better hand in treys. Strict win only (ties excluded).
        if buyer_rank < opponent_rank:
            buyer_wins += 1
            out_cards.update(combo)

    outs = len(out_cards)

    if total_combinations == 0:
        win_probability = 0.0
    else:
        win_probability = buyer_wins / total_combinations

    if win_probability == 0.0 or win_probability >= 1.0:
        odds = 0.0
    else:
        odds = (1 - win_probability) / win_probability

    return {
        "outs": outs,
        "total_combinations": total_combinations,
        "win_probability": round(win_probability, 6),
        "odds": round(odds, 4),
    }
