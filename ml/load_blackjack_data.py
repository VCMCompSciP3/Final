"""
Blackjack Data Loader & Feature Engineer
-----------------------------------------
Dataset: 50 Million Blackjack Hands (dennisho, Kaggle)

Actual CSV columns (confirmed from your file):
  shoe_id, cards_remaining, dealer_upcard, initial_hand,
  dealer_final, dealer_final_value, player_final,
  player_final_value, actions_taken, run_count, true_count, win

Output columns:
  player_total    — hand value at decision point (4-21)
  is_soft         — 1 if hand contains a usable Ace, else 0
  dealer_upcard   — dealer's visible card (2-11)
  can_split       — 1 if first two cards are a pair, else 0
  run_count       — Hi-Lo count at start of round
  action          — 0=Stand 1=Hit 2=Double 3=Split 4=Surrender
"""

import ast
import os
import pandas as pd

# CONFIG
INPUT_FILE  = "/home/compsci/Desktop/blackjack/Final/data/blackjack_simulator.csv"
OUTPUT_FILE = "/home/compsci/Desktop/blackjack/Final/data/blackjack_features.csv"
CHUNK_SIZE  = 200_000

ACTION_MAP = {
    "H": 1,
    "S": 0,
    "D": 2,
    "P": 3,
    "R": 4,
}


def safe_parse(value):
    try:
        return ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        return None


def compute_hand_total(cards):
    total = sum(cards)
    aces  = cards.count(11)
    while total > 21 and aces > 0:
        total -= 10
        aces  -= 1
    return total, aces > 0


def extract_decision_rows(row):
    initial_cards   = safe_parse(row["initial_hand"])
    final_cards_all = safe_parse(row["player_final"])
    actions_all     = safe_parse(row["actions_taken"])

    if not initial_cards or not final_cards_all or not actions_all:
        return
    if not isinstance(initial_cards, list):
        return
    if not isinstance(final_cards_all, list) or not isinstance(actions_all, list):
        return

    dealer_up = row["dealer_up"]
    run_count = row["run_count"]

    for hand_cards, hand_actions in zip(final_cards_all, actions_all):
        if not isinstance(hand_cards, list) or not isinstance(hand_actions, list):
            continue

        play_actions = [a for a in hand_actions if a in ACTION_MAP]
        if not play_actions:
            continue

        current_cards = list(hand_cards[:2]) if len(hand_cards) >= 2 else list(hand_cards)
        if not current_cards:
            continue

        for i, action in enumerate(play_actions):
            total, is_soft = compute_hand_total(current_cards)

            if total > 21:
                break

            can_split = (
                len(current_cards) == 2
                and current_cards[0] == current_cards[1]
            )

            yield {
                "player_total":  total,
                "is_soft":       int(is_soft),
                "dealer_up": int(dealer_up),
                "can_split":     int(can_split),
                "run_count":     int(run_count),
                "action":        ACTION_MAP[action],
            }

            extra_card_index = i
            if extra_card_index < len(hand_cards) - 2:
                current_cards.append(hand_cards[2 + extra_card_index])

            if action in ("S", "D", "R"):
                break


def process():
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        print(f"Cleared existing output file.")

    print(f"Loading '{INPUT_FILE}' in chunks of {CHUNK_SIZE:,} rows...")
    print("This will take a few minutes for 50M rows — grab a coffee.\n")

    total_rows_in  = 0
    total_rows_out = 0
    first_chunk    = True

    reader = pd.read_csv(
        INPUT_FILE,
        header=0,
        chunksize=CHUNK_SIZE,
        dtype={
            "dealer_up":   "int8",
            "run_count":       "int8",
            "cards_remaining": "int16",
        },
    )

    for chunk_num, chunk in enumerate(reader, start=1):

        if chunk_num == 1:
            print(f"Confirmed columns: {list(chunk.columns)}\n")

        rows_out = []
        for _, row in chunk.iterrows():
            for feature_row in extract_decision_rows(row):
                rows_out.append(feature_row)

        if rows_out:
            df_out = pd.DataFrame(rows_out).astype({
                "player_total":  "int8",
                "is_soft":       "int8",
                "dealer_up": "int8",
                "can_split":     "int8",
                "run_count":     "int8",
                "action":        "int8",
            })
            df_out.to_csv(
                OUTPUT_FILE,
                mode="a",
                header=first_chunk,
                index=False,
            )
            first_chunk = False

        total_rows_in  += len(chunk)
        total_rows_out += len(rows_out)

        if chunk_num % 10 == 0:
            print(f"  {total_rows_in:>12,} input rows → "
                  f"{total_rows_out:>12,} decision rows so far...")

    print(f"\nDone!")
    print(f"  Input rows:    {total_rows_in:,}")
    print(f"  Decision rows: {total_rows_out:,}")
    print(f"  Saved to:      {OUTPUT_FILE}")

    print("\nSample of output file (first 10 rows):")
    sample = pd.read_csv(OUTPUT_FILE, nrows=10)
    print(sample.to_string(index=False))

    print("\nAction distribution:")
    counts = pd.read_csv(OUTPUT_FILE, usecols=["action"])["action"].value_counts().sort_index()
    labels = {0: "Stand", 1: "Hit", 2: "Double", 3: "Split", 4: "Surrender"}
    for code, count in counts.items():
        print(f"  {code} ({labels.get(code, '?'):>9}): {count:>12,}")


if __name__ == "__main__":
    process()
