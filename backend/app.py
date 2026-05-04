import os
import joblib
import numpy as np
from flask import Flask, jsonify, request, session
from flask_cors import CORS

from backend.game_engine import BlackjackGame

# ── APP SETUP ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
CORS(app, supports_credentials=True)  # allow frontend on a different port

# ── MODEL LOAD ────────────────────────────────────────────────────────────────
MODEL_PATH = os.path.join(os.path.dirname(__file__), "blackjack_model.pkl")

try:
    model = joblib.load(MODEL_PATH)
    print(f"Model loaded from '{MODEL_PATH}'")
except FileNotFoundError:
    model = None
    print(f"WARNING: Model file not found at '{MODEL_PATH}'. "
          "Run train_blackjack_model.py first. "
          "The /api/ai_suggestion endpoint will return an error until then.")

ACTION_LABELS = {0: "stand", 1: "hit", 2: "double", 3: "split", 4: "surrender"}

# ── IN-MEMORY GAME STORE ─────────────────────────────────────────────────────
# One game object per session. For a single-player local app this is fine.
# If you ever deploy multi-user, swap this for a proper session/DB store.
games: dict[str, BlackjackGame] = {}


def get_game() -> BlackjackGame:
    """Return the BlackjackGame for this session, creating one if needed."""
    sid = session.get("game_id")
    if sid not in games:
        sid = os.urandom(8).hex()
        session["game_id"] = sid
        games[sid] = BlackjackGame()
    return games[sid]


# ── HELPERS ───────────────────────────────────────────────────────────────────

def ok(data: dict):
    """Wrap a successful response."""
    return jsonify({"ok": True, **data})


def err(message: str, status: int = 400):
    """Wrap an error response."""
    return jsonify({"ok": False, "error": message}), status


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.route("/api/new_round", methods=["POST"])
def new_round():
    """
    Start a new round.

    Request body (JSON, optional):
      { "bet": 10 }

    Response:
      Full game state dict (see game_engine._build_state for shape).
    """
    data = request.get_json(silent=True) or {}
    bet  = int(data.get("bet", 1))

    game = get_game()
    try:
        state = game.new_round(bet=bet)
    except ValueError as e:
        return err(str(e))

    return ok({"state": state})


@app.route("/api/action", methods=["POST"])
def player_action():
    """
    Apply a player action.

    Request body (JSON):
      { "action": "hit" }         — one of: hit, stand, double, split, surrender

    Response:
      Full game state dict, including round_result when the round ends.
    """
    data   = request.get_json(silent=True) or {}
    action = data.get("action", "").strip().lower()

    if not action:
        return err("Missing 'action' field.")

    game = get_game()
    try:
        state = game.player_action(action)
    except ValueError as e:
        return err(str(e))

    return ok({"state": state})


@app.route("/api/ai_suggestion", methods=["GET"])
def ai_suggestion():
    """
    Ask the AI model what action to take in the current game state.

    No request body needed — reads from the current session's game state.

    Response:
      {
        "action":      "hit",          — recommended action string
        "action_code": 1,              — numeric code (0–4)
        "confidence":  0.87,           — model's confidence (0–1)
        "state": { ...current state... }
      }

    Used for:
      - Assist mode: show the suggestion as a hint overlay
      - vs AI mode: the AI calls this to decide its own move
    """
    if model is None:
        return err("AI model not loaded. Run train_blackjack_model.py first.", 503)

    game  = get_game()
    state = game._build_state()

    if not state["round_active"]:
        return err("No active round. Call /api/new_round first.")

    # Build the feature vector the model expects
    active_hand = game.player_hands[game.active_hand]
    can_split   = (
        len(active_hand) == 2
        and active_hand[0] == active_hand[1]
        and game.split_count < 3
    )

    features = np.array([[
        state["player_total"],
        state["is_soft"],
        state["dealer_upcard"],
        int(can_split),
        state["run_count"],
    ]])

    action_code  = int(model.predict(features)[0])
    probabilities = model.predict_proba(features)[0]
    confidence   = float(probabilities[action_code])
    action_label = ACTION_LABELS[action_code]

    # Safety check: if the model suggests an illegal action, fall back to hit/stand
    illegal = (
        (action_label == "double"    and not state["can_double"])   or
        (action_label == "split"     and not state["can_split"])    or
        (action_label == "surrender" and not state["can_surrender"])
    )
    if illegal:
        # Re-rank: pick the best legal action
        ranked = sorted(range(len(probabilities)), key=lambda i: -probabilities[i])
        legal_map = {
            "hit": state["can_hit"], "stand": state["can_stand"],
            "double": state["can_double"], "split": state["can_split"],
            "surrender": state["can_surrender"],
        }
        for code in ranked:
            label = ACTION_LABELS.get(code, "")
            if legal_map.get(label, False):
                action_code  = code
                action_label = label
                confidence   = float(probabilities[code])
                break

    return ok({
        "action":      action_label,
        "action_code": action_code,
        "confidence":  round(confidence, 4),
        "state":       state,
    })


@app.route("/api/state", methods=["GET"])
def get_state():
    """Return the current game state without taking any action."""
    game  = get_game()
    state = game._build_state()
    return ok({"state": state})


@app.route("/api/reset", methods=["POST"])
def reset_game():
    """
    Reset the game: fresh shoe, balance restored to 1000.
    Useful for starting a new session without refreshing the browser.
    """
    sid = session.get("game_id")
    if sid in games:
        del games[sid]
    game = get_game()   # creates a fresh BlackjackGame
    return ok({"state": game._build_state(), "message": "Game reset."})


# ── DEV SERVER ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)