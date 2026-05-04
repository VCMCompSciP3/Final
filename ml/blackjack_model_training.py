"""
Blackjack AI — Supervised Learning Trainer
-------------------------------------------
Input:  blackjack_features.csv  (output from load_blackjack_data.py)
Output: blackjack_model.pkl     (trained model, ready to load in Flask)
        blackjack_model_report.txt (accuracy + basic strategy validation)

Model: Random Forest Classifier (scikit-learn)
  — No GPU needed
  — Trains on a 5M-row sample (plenty for this feature space)
  — Validates against the known optimal basic strategy chart

Install dependencies first:
  pip install pandas scikit-learn joblib
"""

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

# ── CONFIG ───────────────────────────────────────────────────────────────────
INPUT_FILE   = "/home/compsci/Desktop/blackjack/Final/data/blackjack_features.csv"   # from load_blackjack_data.py
MODEL_FILE   = "/home/compsci/Desktop/blackjack/Final/data/blackjack_model.pkl"      # where to save the trained model
REPORT_FILE  = "/home/compsci/Desktop/blackjack/Final/data/blackjack_model_report.txt"
SAMPLE_ROWS  = 5_000_000   # rows to train on (5M is plenty; raise if you want)
RANDOM_SEED  = 42
# ─────────────────────────────────────────────────────────────────────────────

# Action label map (must match load_blackjack_data.py)
ACTION_LABELS = {0: "Stand", 1: "Hit", 2: "Double", 3: "Split", 4: "Surrender"}

# ── BASIC STRATEGY REFERENCE TABLE ───────────────────────────────────────────
# Ground truth: optimal action for every (player_total, is_soft, dealer_upcard)
# Source: https://wizardofodds.com/games/blackjack/strategy/4-decks/
# Format: (player_total, is_soft, dealer_upcard) → action code
#   0=Stand, 1=Hit, 2=Double, 4=Surrender
# Pairs (split) handled separately below.
# This is a representative subset of key states for validation.

def basic_strategy(player_total, is_soft, dealer_upcard, can_split):
    """
    Returns the basic strategy action code for a given game state.
    Covers hard totals, soft totals, and pairs.
    dealer_upcard: 2–10, 11=Ace
    """
    d = dealer_upcard

    # --- Pairs ---
    if can_split:
        card = player_total // 2  # value of each card in the pair
        if card == 11:  return 3  # Always split Aces
        if card == 8:   return 3  # Always split 8s
        if card == 10:  return 0  # Never split 10s
        if card == 5:           # Treat as hard 10
            return 2 if d in range(2, 10) else 1
        if card == 4:
            return 3 if d in (5, 6) else 1
        if card == 9:
            return 0 if d in (7, 10, 11) else 3
        if card == 7:
            return 3 if d in range(2, 8) else 1
        if card == 6:
            return 3 if d in range(2, 7) else 1
        if card == 3:
            return 3 if d in range(2, 8) else 1
        if card == 2:
            return 3 if d in range(2, 8) else 1

    # --- Soft totals (hand contains usable Ace) ---
    if is_soft:
        if player_total >= 19:  return 0  # Soft 19+ always Stand
        if player_total == 18:
            if d in range(2, 7):  return 2   # Double vs 2–6
            if d in (7, 8):       return 0   # Stand vs 7, 8
            return 1                          # Hit vs 9, 10, Ace
        if player_total == 17:
            return 2 if d in range(3, 7) else 1
        if player_total in (15, 16):
            return 2 if d in (4, 5, 6) else 1
        if player_total in (13, 14):
            return 2 if d in (5, 6) else 1
        return 1  # Soft 12 or lower: always Hit

    # --- Hard totals ---
    if player_total >= 17:  return 0   # Always Stand
    if player_total == 16:
        if d in (9, 10, 11):  return 4  # Surrender
        if d in range(2, 7):  return 0  # Stand
        return 1                         # Hit vs 7, 8
    if player_total == 15:
        if d in (10, 11):  return 4  # Surrender vs 10, Ace
        if d in range(2, 7): return 0
        return 1
    if player_total == 13:
        return 0 if d in range(2, 7) else 1
    if player_total == 14:
        return 0 if d in range(2, 7) else 1
    if player_total == 12:
        return 0 if d in (4, 5, 6) else 1
    if player_total == 11:
        return 2 if d != 11 else 1
    if player_total == 10:
        return 2 if d in range(2, 10) else 1
    if player_total == 9:
        return 2 if d in range(3, 7) else 1
    return 1  # Hard 8 or lower: always Hit


def validate_against_basic_strategy(model, feature_cols):
    """
    Test model predictions against the optimal basic strategy chart
    across all meaningful game states (~340 combinations).
    Returns the match percentage.
    """
    print("\nValidating against basic strategy chart...")

    states = []
    for total in range(4, 22):
        for is_soft in (0, 1):
            if is_soft and total < 12:
                continue  # soft totals start at 12 (Ace+Ace=soft 12)
            if is_soft and total > 21:
                continue
            for dealer in range(2, 12):
                for can_split in (0, 1):
                    if can_split and total % 2 != 0:
                        continue  # pairs always have even totals
                    states.append({
                        "player_total":  total,
                        "is_soft":       is_soft,
                        "dealer_upcard": dealer,
                        "can_split":     can_split,
                        "run_count":     0,  # neutral count for reference
                    })

    df_states = pd.DataFrame(states)
    model_preds = model.predict(df_states[feature_cols])

    matches = 0
    mismatches = []
    for i, row in df_states.iterrows():
        expected = basic_strategy(
            int(row["player_total"]),
            bool(row["is_soft"]),
            int(row["dealer_upcard"]),
            bool(row["can_split"]),
        )
        predicted = model_preds[i - df_states.index[0]]
        if predicted == expected:
            matches += 1
        else:
            mismatches.append({
                "player_total":  int(row["player_total"]),
                "is_soft":       bool(row["is_soft"]),
                "dealer_upcard": int(row["dealer_upcard"]),
                "can_split":     bool(row["can_split"]),
                "expected":      ACTION_LABELS[expected],
                "predicted":     ACTION_LABELS[predicted],
            })

    pct = matches / len(df_states) * 100
    print(f"  Basic strategy match: {matches}/{len(df_states)} = {pct:.1f}%")
    if mismatches:
        print(f"  Top mismatches (first 10):")
        for m in mismatches[:10]:
            soft_str = "soft" if m["is_soft"] else "hard"
            split_str = " (pair)" if m["can_split"] else ""
            print(f"    {soft_str} {m['player_total']}{split_str} vs dealer {m['dealer_upcard']}: "
                  f"expected {m['expected']}, got {m['predicted']}")
    return pct, mismatches


def main():
    # ── 1. LOAD DATA ──────────────────────────────────────────────────────────
    print(f"Loading up to {SAMPLE_ROWS:,} rows from '{INPUT_FILE}'...")
    df = pd.read_csv(INPUT_FILE, nrows=SAMPLE_ROWS, dtype={
        "player_total":  "int8",
        "is_soft":       "int8",
        "dealer_upcard": "int8",
        "can_split":     "int8",
        "run_count":     "int16",
        "action":        "int8",
    })
    print(f"  Loaded {len(df):,} rows.")
    print(f"  Action distribution:\n{df['action'].value_counts().sort_index()}\n")

    # ── 2. FEATURES & TARGET ─────────────────────────────────────────────────
    feature_cols = ["player_total", "is_soft", "dealer_upcard", "can_split", "run_count"]
    target_col   = "action"

    X = df[feature_cols]
    y = df[target_col]

    # ── 3. TRAIN / TEST SPLIT ─────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=RANDOM_SEED, stratify=y
    )
    print(f"Train size: {len(X_train):,}   Test size: {len(X_test):,}")

    # ── 4. TRAIN MODEL ────────────────────────────────────────────────────────
    print("\nTraining Random Forest... (this takes ~3–8 minutes on a laptop)")
    model = RandomForestClassifier(
        n_estimators=200,       # number of trees — more = better but slower
        max_depth=20,           # max tree depth — prevents overfitting
        min_samples_leaf=50,    # min samples per leaf — smooths rare states
        n_jobs=-1,              # use all CPU cores
        random_state=RANDOM_SEED,
        verbose=1,
    )
    model.fit(X_train, y_train)
    print("Training complete.")

    # ── 5. EVALUATE ───────────────────────────────────────────────────────────
    print("\nEvaluating on test set...")
    y_pred = model.predict(X_test)
    report = classification_report(
        y_test, y_pred,
        target_names=[ACTION_LABELS[i] for i in sorted(ACTION_LABELS)],
    )
    print(report)

    # ── 6. VALIDATE VS BASIC STRATEGY ────────────────────────────────────────
    bs_match_pct, mismatches = validate_against_basic_strategy(model, feature_cols)

    # ── 7. FEATURE IMPORTANCE ────────────────────────────────────────────────
    print("\nFeature importances:")
    for feat, imp in sorted(zip(feature_cols, model.feature_importances_),
                             key=lambda x: -x[1]):
        print(f"  {feat:<20} {imp:.4f}")

    # ── 8. SAVE MODEL ─────────────────────────────────────────────────────────
    joblib.dump(model, MODEL_FILE)
    print(f"\nModel saved to '{MODEL_FILE}'")

    # ── 9. SAVE REPORT ───────────────────────────────────────────────────────
    with open(REPORT_FILE, "w") as f:
        f.write("BLACKJACK AI — TRAINING REPORT\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Training rows: {len(X_train):,}\n")
        f.write(f"Test rows:     {len(X_test):,}\n\n")
        f.write("Classification Report:\n")
        f.write(report + "\n")
        f.write(f"Basic Strategy Match: {bs_match_pct:.1f}%\n\n")
        if mismatches:
            f.write("Mismatches vs Basic Strategy:\n")
            for m in mismatches:
                f.write(f"  {m}\n")
    print(f"Report saved to '{REPORT_FILE}'")

    # ── 10. QUICK DEMO ────────────────────────────────────────────────────────
    print("\n── Quick demo: what would the AI do? ──")
    demo_hands = [
        {"player_total": 16, "is_soft": 0, "dealer_upcard": 10, "can_split": 0, "run_count": 0},
        {"player_total": 11, "is_soft": 0, "dealer_upcard":  6, "can_split": 0, "run_count": 0},
        {"player_total": 18, "is_soft": 1, "dealer_upcard":  9, "can_split": 0, "run_count": 0},
        {"player_total": 16, "is_soft": 0, "dealer_upcard":  7, "can_split": 1, "run_count": 0},
    ]
    demo_df = pd.DataFrame(demo_hands)
    preds   = model.predict(demo_df[feature_cols])
    for hand, pred in zip(demo_hands, preds):
        soft = "soft" if hand["is_soft"] else "hard"
        pair = " (pair)" if hand["can_split"] else ""
        print(f"  {soft} {hand['player_total']}{pair} vs dealer {hand['dealer_upcard']}"
              f"  →  {ACTION_LABELS[pred]}")


if __name__ == "__main__":
    main()