"""
Blackjack Data Loader & Feature Engineer
-----------------------------------------
Dataset: 50 Million Blackjack Hands (dennisho, Kaggle)
File:    blackjack_simulator.csv (~3.89 GB)

This script:
  1. Loads the CSV in memory-efficient chunks
  2. Parses the nested list columns (ast.literal_eval)
  3. Engineers features for supervised learning
  4. Extracts one row per DECISION POINT (not per hand)
  5. Saves a clean, model-ready CSV: blackjack_features.csv

Output columns:
  player_total    — hand value at decision point (4–21)
  is_soft         — True if hand contains a usable Ace counted as 11
  dealer_upcard   — dealer's visible card (2–11)
  can_split       — True if first two cards are a pair
  run_count       — Hi-Lo count at start of round (card counting signal)
  action          — target label: 0=Stand, 1=Hit, 2=Double, 3=Split, 4=Surrender
"""

import ast
import pandas as pd

# ── CONFIG ──────────────────────────────────────────────────────────────────
INPUT_FILE  = "/home/compsci/Desktop/blackjack/Final/data/blackjack_simulator.csv"
OUTPUT_FILE = "/home/compsci/Desktop/blackjack/Final/data/blackjack_features.csv"
CHUNK_SIZE  = 200_000                     # rows per chunk (tune to your RAM)
# ────────────────────────────────────────────────────────────────────────────

# Maps raw column positions to readable names.
# Based on the Kaggle dataset description (12 columns, 0-indexed):
COLUMN_NAMES = [
    "shoe_id",            # 0  — shoe identifier
    "cards_remaining",    # 1  — cards left in shoe at round start
    "dealer_upcard",      # 2  — dealer's visible card
    "player_initial",     # 3  — player's first 2 cards e.g. [6, 10]
    "dealer_final_cards", # 4  — dealer's full hand e.g. [9, 10]
    "dealer_final_value", # 5  — dealer total or 'BJ'
    "player_final_cards", # 6  — player hand(s) e.g. [[6, 10, 4]]
    "player_final_values",# 7  — player totals e.g. [20]
    "actions",            # 8  — moves taken e.g. [['H', 'S']]
    "run_count",          # 9  — Hi-Lo running count
]

# Action label encoding
ACTION_MAP = {
    "H": 1,  # Hit
    "S": 0,  # Stand
    "D": 2,  # Double Down
    "P": 3,  # Split
    "R": 4,  # Surrender
    # N (No Insurance) and I (Insurance) are skipped — not playing decisions
}


def safe_parse(value):
    """Parse a stringified Python list. Returns None on failure."""
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return None


def compute_hand_total(cards):
    """
    Given a list of card values (Aces always stored as 11),
    compute the correct blackjack total (Ace = 1 or 11).
    Returns (total, is_soft).
    """
    total = sum(cards)
    aces  = cards.count(11)
    # Reduce Aces from 11 → 1 as needed to stay under 22
    while total > 21 and aces > 0:
        total -= 10
        aces  -= 1
    is_soft = aces > 0  # True if at least one Ace still counts as 11
    return total, is_soft


def extract_decision_rows(row):
    """
    A single CSV row = one full hand. But a hand can have multiple
    decision points (e.g. H, H, S = three actions, two decisions before
    the final stand).

    This function reconstructs each decision point by replaying the
    action sequence against the cards dealt, yielding one feature row
    per meaningful action (Hit, Stand, Double, Split, Surrender).

    Yields dicts with keys matching the output columns.
    """
    # Parse list columns
    initial_cards  = safe_parse(str(row["player_initial"]))
    final_cards_all = safe_parse(str(row["player_final_cards"]))
    actions_all     = safe_parse(str(row["actions"]))

    if not initial_cards or not final_cards_all or not actions_all:
        return  # skip malformed rows

    dealer_up  = row["dealer_upcard"]
    run_count  = row["run_count"]

    # Handle split hands: each is a separate action sequence
    for hand_cards, hand_actions in zip(final_cards_all, actions_all):

        # Filter to playing decisions only (skip N/I insurance calls)
        play_actions = [a for a in hand_actions if a in ACTION_MAP]
        if not play_actions:
            continue

        # Reconstruct the hand card by card to get state at each decision
        # Starting point: the two initial cards for the first hand
        # For split hands after the first, we start with the split card + one new card
        # We approximate this by using the first two cards of hand_cards
        current_cards = list(hand_cards[:2]) if len(hand_cards) >= 2 else list(hand_cards)

        for i, action in enumerate(play_actions):
            total, is_soft = compute_hand_total(current_cards)

            # Skip decisions on busted hands or post-21 hands
            # (these can appear in data after a hit pushes over 21)
            if total > 21:
                break

            can_split = (
                len(current_cards) == 2 and
                current_cards[0] == current_cards[1]
            )

            yield {
                "player_total":  total,
                "is_soft":       int(is_soft),
                "dealer_upcard": int(dealer_up),
                "can_split":     int(can_split),
                "run_count":     int(run_count),
                "action":        ACTION_MAP[action],
            }

            # Advance the hand state: add the next card dealt
            # Cards after the first two are in hand_cards[2:]
            next_card_index = i  # 0-indexed extra cards
            if next_card_index < len(hand_cards) - 2:
                current_cards.append(hand_cards[2 + next_card_index])

            # After Stand/Double/Surrender the hand is over
            if action in ("S", "D", "R"):
                break


def process():
    print(f"Loading '{INPUT_FILE}' in chunks of {CHUNK_SIZE:,} rows...")
    print("This will take a few minutes for 50M rows — grab a coffee.\n")

    total_rows_in   = 0
    total_rows_out  = 0
    first_chunk     = True

    reader = pd.read_csv(
        INPUT_FILE,
        header=0,                    # first row is the header
        chunksize=CHUNK_SIZE,
        dtype={
            "dealer_upcard": "int8",
            "run_count":     "int16",
            "cards_remaining": "int16",
        },
        # If the CSV has no header, replace header=0 with:
        # header=None, names=COLUMN_NAMES
    )

    for chunk_num, chunk in enumerate(reader, start=1):
        rows_out = []

        for _, row in chunk.iterrows():
            for feature_row in extract_decision_rows(row):
                rows_out.append(feature_row)

        if rows_out:
            df_out = pd.DataFrame(rows_out).astype({
                "player_total":  "int8",
                "is_soft":       "int8",
                "dealer_upcard": "int8",
                "can_split":     "int8",
                "run_count":     "int16",
                "action":        "int8",
            })

            df_out.to_csv(
                OUTPUT_FILE,
                mode="a",
                header=first_chunk,  # write header only on first chunk
                index=False,
            )
            first_chunk = False

        total_rows_in  += len(chunk)
        total_rows_out += len(rows_out)

        if chunk_num % 10 == 0:
            print(f"  Processed {total_rows_in:>12,} input rows → "
                  f"{total_rows_out:>12,} decision rows so far...")

    print(f"\nDone!")
    print(f"  Input rows:    {total_rows_in:,}")
    print(f"  Decision rows: {total_rows_out:,}")
    print(f"  Saved to:      {OUTPUT_FILE}")

    # Quick sanity check on the output
    print("\nSample of output file:")
    sample = pd.read_csv(OUTPUT_FILE = "/home/compsci/Desktop/blackjack/Final/data/blackjack_features.csv"
    print(sample.to_string(index=False))

    print("\nAction distribution:")
    action_counts = pd.read_csv(OUTPUT_FILE = "/home/compsci/Desktop/blackjack/Final/data/blackjack_features.csv"
    labels = {0: "Stand", 1: "Hit", 2: "Double", 3: "Split", 4: "Surrender"}
    for code, count in action_counts.items():
        print(f"  {code} ({labels[code]:>9}): {count:>12,}")


if __name__ == "__main__":
    process()