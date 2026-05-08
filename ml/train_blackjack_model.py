"""
Blackjack AI — Supervised Learning Trainer
-------------------------------------------
Input:  ../data/blackjack_features.csv   (output of load_blackjack_data.py)
Output: ../ml/blackjack_model.pkl        (trained model, loaded by Flask)
        ../ml/blackjack_model_report.txt (accuracy + basic strategy validation)

Model: Random Forest Classifier (scikit-learn)
  — No GPU needed
  — Trains on a 5M-row sample (plenty for this small feature space)
  — Validates predictions against the known optimal basic strategy chart

Install:
  pip install pandas scikit-learn joblib

FIXES vs previous version:
  - Removed unused numpy import
  - Fixed fragile index arithmetic in validate_against_basic_strategy
    (was: model_preds[i - df_states.index[0]] — breaks on non-contiguous index)
    (now: uses enumerate, fully index-safe)
  - Updated file paths to match project folder structure
"""

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

# ── CONFIG ───────────────────────────────────────────────────────────────────
INPUT_FILE   = "/home/compsci/Desktop/blackjack/Final/data/blackjack_features.csv"
MODEL_FILE  = "/home/compsci/Desktop/blackjack/Final/ml/blackjack_model.pkl"
REPORT_FILE = "/home/compsci/Desktop/blackjack/Final/ml/blackjack_model_report.txt"
SAMPLE_ROWS  = 5_000_000   # 5M rows is plenty; raise if you want more coverage
RANDOM_SEED  = 42
# ─────────────────────────────────────────────────────────────────────────────

ACTION_LABELS = {0: "Stand", 1: "Hit", 2: "Double", 3: "Split", 4: "Surrender"}


def basic_strategy(player_total, is_soft, dealer_up, can_split):
    """
    Returns the basic strategy action code for a given game state.
    Source: https://wizardofodds.com/games/blackjack/strategy/4-decks/
    dealer_up: 2–10, 11 = Ace
    """
    d = dealer_up

    # --- Pairs ---
    if can_split:
        card = player_total // 2
        if card == 11: return 3                                    # always split Aces
        if card == 8:  return 3                                    # always split 8s
        if card == 10: return 0                                    # never split 10s
        if card == 5:  return 2 if d in range(2, 10) else 1       # treat as hard 10
        if card == 4:  return 3 if d in (5, 6) else 1
        if card == 9:  return 0 if d in (7, 10, 11) else 3
        if card == 7:  return 3 if d in range(2, 8) else 1
        if card == 6:  return 3 if d in range(2, 7) else 1
        if card == 3:  return 3 if d in range(2, 8) else 1
        if card == 2:  return 3 if d in range(2, 8) else 1

    # --- Soft totals ---
    if is_soft:
        if player_total >= 19: return 0
        if player_total == 18:
            if d in range(2, 7): return 2
            if d in (7, 8):      return 0
            return 1
        if player_total == 17:
            return 2 if d in range(3, 7) else 1
        if player_total in (15, 16):
            return 2 if d in (4, 5, 6) else 1
        if player_total in (13, 14):
            return 2 if d in (5, 6) else 1
        return 1

    # --- Hard totals ---
    if player_total >= 17: return 0
    if player_total == 16:
        if d in (9, 10, 11):    return 4   # Surrender
        if d in range(2, 7):    return 0   # Stand
        return 1                            # Hit vs 7, 8
    if player_total == 15:
        if d in (10, 11):       return 4   # Surrender
        if d in range(2, 7):    return 0
        return 1
    if player_total == 14:      return 0 if d in range(2, 7) else 1
    if player_total == 13:      return 0 if d in range(2, 7) else 1
    if player_total == 12:      return 0 if d in (4, 5, 6) else 1
    if player_total == 11:      return 2 if d != 11 else 1
    if player_total == 10:      return 2 if d in range(2, 10) else 1
    if player_total == 9:       return 2 if d in range(3, 7) else 1
    return 1  # hard 8 or lower: always Hit


def validate_against_basic_strategy(model, feature_cols):
    """
    Runs the trained model over all meaningful game states and compares
    each prediction to the known optimal basic strategy action.
    Returns (match_percentage, list_of_mismatches).
    """
    print("\nValidating against basic strategy chart...")

    states = []
    for total in range(4, 22):
        for is_soft in (0, 1):
            if is_soft and total < 12:
                continue  # soft totals start at 12 (Ace + Ace)
            for dealer in range(2, 12):
                for can_split in (0, 1):
                    if can_split and total % 2 != 0:
                        continue  # pairs must have even totals
                    states.append({
                        "player_total":  total,
                        "is_soft":       is_soft,
                        "dealer_up": dealer,
                        "can_split":     can_split,
                        "run_count":     0,  # neutral count for chart comparison
                    })

    df_states   = pd.DataFrame(states)
    model_preds = model.predict(df_states[feature_cols])

    matches    = 0
    mismatches = []

    # FIX: use enumerate instead of index arithmetic — safe on any index shape
    for idx, (_, row) in enumerate(df_states.iterrows()):
        expected  = basic_strategy(
            int(row["player_total"]),
            bool(row["is_soft"]),
            int(row["dealer_up"]),
            bool(row["can_split"]),
        )
        predicted = int(model_preds[idx])

        if predicted == expected:
            matches += 1
        else:
            mismatches.append({
                "player_total":  int(row["player_total"]),
                "is_soft":       bool(row["is_soft"]),
                "dealer_up": int(row["dealer_up"]),
                "can_split":     bool(row["can_split"]),
                "expected":      ACTION_LABELS[expected],
                "predicted":     ACTION_LABELS[predicted],
            })

    pct = matches / len(df_states) * 100
    print(f"  Basic strategy match: {matches}/{len(df_states)} = {pct:.1f}%")

    if mismatches:
        print(f"  Top mismatches (first 10):")
        for m in mismatches[:10]:
            soft_str  = "soft" if m["is_soft"] else "hard"
            pair_str  = " (pair)" if m["can_split"] else ""
            print(f"    {soft_str} {m['player_total']}{pair_str} "
                  f"vs dealer {m['dealer_up']}: "
                  f"expected {m['expected']}, got {m['predicted']}")

    return pct, mismatches


def main():
    # ── 1. LOAD ───────────────────────────────────────────────────────────────
    print(f"Loading up to {SAMPLE_ROWS:,} rows from '{INPUT_FILE}'...")
    df = pd.read_csv(INPUT_FILE, nrows=SAMPLE_ROWS, dtype={
        "player_total":  "int8",
        "is_soft":       "int8",
        "dealer_up": "int8",
        "can_split":     "int8",
        "run_count":     "int8",
        "action":        "int8",
    })
    print(f"  Loaded {len(df):,} rows.")
    print(f"  Action distribution:\n{df['action'].value_counts().sort_index()}\n")

    # ── 2. FEATURES & TARGET ─────────────────────────────────────────────────
    feature_cols = ["player_total", "is_soft", "dealer_up", "can_split", "run_count"]
    target_col   = "action"

    X = df[feature_cols]
    y = df[target_col]

    # ── 3. TRAIN / TEST SPLIT ─────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=RANDOM_SEED, stratify=y
    )
    print(f"Train size: {len(X_train):,}   Test size: {len(X_test):,}")

    # ── 4. TRAIN ──────────────────────────────────────────────────────────────
    print("\nTraining Random Forest... (expect 3–8 min on a laptop)")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_leaf=50,
        n_jobs=-1,              # uses all CPU cores
        random_state=RANDOM_SEED,
        verbose=1,
    )
    model.fit(X_train, y_train)
    print("Training complete.")

    # ── 5. EVALUATE ───────────────────────────────────────────────────────────
    print("\nEvaluating on held-out test set...")
    y_pred = model.predict(X_test)
    report = classification_report(
        y_test, y_pred,
        target_names=[ACTION_LABELS[i] for i in sorted(ACTION_LABELS)],
    )
    print(report)

    # ── 6. BASIC STRATEGY VALIDATION ─────────────────────────────────────────
    bs_pct, mismatches = validate_against_basic_strategy(model, feature_cols)

    # ── 7. FEATURE IMPORTANCE ────────────────────────────────────────────────
    print("\nFeature importances:")
    for feat, imp in sorted(zip(feature_cols, model.feature_importances_),
                             key=lambda x: -x[1]):
        print(f"  {feat:<20} {imp:.4f}")

    # ── 8. SAVE MODEL ─────────────────────────────────────────────────────────
    joblib.dump(model, MODEL_FILE)
    print(f"\nModel saved → '{MODEL_FILE}'")

    # ── 9. SAVE REPORT ───────────────────────────────────────────────────────
    with open(REPORT_FILE, "w") as f:
        f.write("BLACKJACK AI — TRAINING REPORT\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Training rows:  {len(X_train):,}\n")
        f.write(f"Test rows:      {len(X_test):,}\n\n")
        f.write("Classification Report:\n")
        f.write(report + "\n")
        f.write(f"Basic Strategy Match: {bs_pct:.1f}%\n\n")
        if mismatches:
            f.write("Mismatches vs Basic Strategy:\n")
            for m in mismatches:
                f.write(f"  {m}\n")
    print(f"Report saved  → '{REPORT_FILE}'")

    # ── 10. QUICK DEMO ────────────────────────────────────────────────────────
    print("\n── Quick demo ──")
    demo_hands = [
        {"player_total": 16, "is_soft": 0, "dealer_up": 10, "can_split": 0, "run_count": 0},
        {"player_total": 11, "is_soft": 0, "dealer_up":  6, "can_split": 0, "run_count": 0},
        {"player_total": 18, "is_soft": 1, "dealer_up":  9, "can_split": 0, "run_count": 0},
        {"player_total": 16, "is_soft": 0, "dealer_up":  7, "can_split": 1, "run_count": 0},
    ]
    demo_df = pd.DataFrame(demo_hands)
    preds   = model.predict(demo_df[feature_cols])
    for hand, pred in zip(demo_hands, preds):
        soft = "soft" if hand["is_soft"] else "hard"
        pair = " (pair)" if hand["can_split"] else ""
        print(f"  {soft} {hand['player_total']}{pair} vs dealer {hand['dealer_up']}"
              f"  →  {ACTION_LABELS[int(pred)]}")


if __name__ == "__main__":
    main()
