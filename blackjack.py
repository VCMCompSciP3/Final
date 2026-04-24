import tkinter as tk
import random

# ─── DECK ────────────────────────────────────────────────────────────────────

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

def create_deck():
    return [{'suit': s, 'rank': r} for s in SUITS for r in RANKS]

def shuffle(deck):
    random.shuffle(deck)
    return deck

# ─── HAND VALUE ───────────────────────────────────────────────────────────────

def hand_value(hand):
    total = 0
    aces = 0
    for card in hand:
        if card['rank'] == 'A':
            aces += 1
            total += 11
        elif card['rank'] in ('J', 'Q', 'K'):
            total += 10
        else:
            total += int(card['rank'])
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

# ─── GAME ─────────────────────────────────────────────────────────────────────

class BlackjackGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Blackjack")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e4d35")

        self.deck = []
        self.player_hand = []
        self.dealer_hand = []
        self.status = "idle"  # idle | playing | ended

        self._build_ui()
        self._render()

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        PAD = dict(padx=16, pady=8)

        # Title
        tk.Label(
            self.root, text="BLACKJACK",
            font=("Georgia", 26, "bold"),
            bg="#1e4d35", fg="#c9a84c"
        ).pack(pady=(24, 4))

        # Dealer section
        tk.Label(
            self.root, text="DEALER",
            font=("Georgia", 11), bg="#1e4d35", fg="#a8c4b0"
        ).pack()

        self.dealer_score_label = tk.Label(
            self.root, text="",
            font=("Georgia", 13, "bold"), bg="#1e4d35", fg="#f0ead8"
        )
        self.dealer_score_label.pack()

        self.dealer_frame = tk.Frame(self.root, bg="#1e4d35")
        self.dealer_frame.pack(pady=8)

        # Divider
        tk.Frame(self.root, bg="#c9a84c", height=1, width=460).pack(pady=8)

        # Player section
        tk.Label(
            self.root, text="YOU",
            font=("Georgia", 11), bg="#1e4d35", fg="#a8c4b0"
        ).pack()

        self.player_score_label = tk.Label(
            self.root, text="",
            font=("Georgia", 13, "bold"), bg="#1e4d35", fg="#f0ead8"
        )
        self.player_score_label.pack()

        self.player_frame = tk.Frame(self.root, bg="#1e4d35")
        self.player_frame.pack(pady=8)

        # Message
        self.message_label = tk.Label(
            self.root, text="",
            font=("Georgia", 14, "bold"), bg="#1e4d35", fg="#e8c97a",
            height=2
        )
        self.message_label.pack()

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1e4d35")
        btn_frame.pack(pady=8)

        btn_style = dict(
            font=("Georgia", 12, "bold"),
            width=8, height=1,
            relief="flat", cursor="hand2",
            bd=0
        )

        self.btn_deal = tk.Button(
            btn_frame, text="Deal",
            bg="#c9a84c", fg="#1a3a2a",
            activebackground="#e8c97a", activeforeground="#1a3a2a",
            command=self.deal, **btn_style
        )
        self.btn_deal.grid(row=0, column=0, padx=8)

        self.btn_hit = tk.Button(
            btn_frame, text="Hit",
            bg="#245c3e", fg="#f0ead8",
            activebackground="#2e7a50", activeforeground="#f0ead8",
            command=self.hit, **btn_style
        )
        self.btn_hit.grid(row=0, column=1, padx=8)

        self.btn_stand = tk.Button(
            btn_frame, text="Stand",
            bg="#245c3e", fg="#f0ead8",
            activebackground="#2e7a50", activeforeground="#f0ead8",
            command=self.stand, **btn_style
        )
        self.btn_stand.grid(row=0, column=2, padx=8)

        # AI suggestion box — partner will hook into this
        tk.Label(
            self.root, text="AI ASSISTANT",
            font=("Georgia", 9), bg="#1e4d35", fg="#a8c4b0"
        ).pack(pady=(12, 0))

        self.ai_label = tk.Label(
            self.root,
            text="🤖 AI assistant ready...",
            font=("Georgia", 11, "italic"),
            bg="#163828", fg="#a8c4b0",
            width=46, height=2,
            relief="flat", wraplength=400
        )
        self.ai_label.pack(pady=(4, 20))

    # ── CARD WIDGET ───────────────────────────────────────────────────────────

    def _card_widget(self, parent, card, face_down=False):
        frame = tk.Frame(
            parent,
            bg="#fdfaf4", width=64, height=92,
            relief="raised", bd=1
        )
        frame.pack_propagate(False)

        if face_down:
            tk.Label(
                frame, text="🂠",
                font=("Georgia", 28), bg="#1a4a6e", fg="#1a4a6e",
                width=3
            ).pack(expand=True)
            frame.configure(bg="#1a4a6e")
        else:
            is_red = card['suit'] in ('♥', '♦')
            color = "#c0392b" if is_red else "#1a1a1a"

            tk.Label(
                frame,
                text=f"{card['rank']}\n{card['suit']}",
                font=("Georgia", 14, "bold"),
                bg="#fdfaf4", fg=color,
                justify="center"
            ).pack(expand=True)

        return frame

    # ── RENDER ────────────────────────────────────────────────────────────────

    def _render(self):
        is_ended = self.status == "ended"

        # Clear card frames
        for widget in self.dealer_frame.winfo_children():
            widget.destroy()
        for widget in self.player_frame.winfo_children():
            widget.destroy()

        # Dealer cards
        for i, card in enumerate(self.dealer_hand):
            face_down = (i == 1 and not is_ended)
            w = self._card_widget(self.dealer_frame, card, face_down)
            w.pack(side="left", padx=4)

        # Player cards
        for card in self.player_hand:
            w = self._card_widget(self.player_frame, card)
            w.pack(side="left", padx=4)

        # Scores
        if self.dealer_hand:
            if is_ended:
                d_score = f"Dealer: {hand_value(self.dealer_hand)}"
            else:
                first = self.dealer_hand[0]
                v = 11 if first['rank'] == 'A' else (10 if first['rank'] in ('J','Q','K') else int(first['rank']))
                d_score = f"Dealer: {v}+"
            self.dealer_score_label.config(text=d_score)
        else:
            self.dealer_score_label.config(text="")

        if self.player_hand:
            self.player_score_label.config(text=f"You: {hand_value(self.player_hand)}")
        else:
            self.player_score_label.config(text="")

        # Buttons
        playing = self.status == "playing"
        idle_or_ended = self.status in ("idle", "ended")

        self.btn_deal.config(state="normal" if idle_or_ended else "disabled",
                             bg="#c9a84c" if idle_or_ended else "#7a6530")
        self.btn_hit.config(state="normal" if playing else "disabled",
                            bg="#245c3e" if playing else "#1a3a2a")
        self.btn_stand.config(state="normal" if playing else "disabled",
                              bg="#245c3e" if playing else "#1a3a2a")

    # ── ACTIONS ───────────────────────────────────────────────────────────────

    def deal(self):
        self.deck = shuffle(create_deck())
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.status = "playing"
        self.message_label.config(text="")
        self.ai_label.config(text="🤖 Thinking...")
        self._render()
        self._notify_ai("deal")

        if hand_value(self.player_hand) == 21:
            self._end_round("blackjack")

    def hit(self):
        if self.status != "playing":
            return
        self.player_hand.append(self.deck.pop())
        total = hand_value(self.player_hand)
        self._render()
        self._notify_ai("hit")

        if total > 21:
            self._end_round("bust")
        elif total == 21:
            self.stand()

    def stand(self):
        if self.status != "playing":
            return
        self.status = "dealer"
        self._render()
        self._run_dealer()

    def _run_dealer(self):
        if hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
            self._render()
            self.root.after(600, self._run_dealer)
        else:
            self._determine_winner()

    def _determine_winner(self):
        p = hand_value(self.player_hand)
        d = hand_value(self.dealer_hand)

        if d > 21:
            self._end_round("dealer-bust")
        elif p > d:
            self._end_round("win")
        elif d > p:
            self._end_round("lose")
        else:
            self._end_round("push")

    def _end_round(self, result):
        self.status = "ended"
        messages = {
            "blackjack":   "🃏 Blackjack! You win!",
            "bust":        "💥 Bust! You went over 21.",
            "dealer-bust": "🎉 Dealer busted! You win!",
            "win":         "✅ You win!",
            "lose":        "❌ Dealer wins.",
            "push":        "🤝 It's a tie!",
        }
        self.message_label.config(text=messages.get(result, ""))
        self._render()
        self._notify_ai("end", result)

    # ── AI HOOK ───────────────────────────────────────────────────────────────
    # Your partner hooks in here. They can set self.on_ai_turn to a function
    # that receives the game state and updates self.ai_label with advice.

    def _notify_ai(self, event, data=None):
        if hasattr(self, 'on_ai_turn') and callable(self.on_ai_turn):
            state = {
                "event":         event,
                "data":          data,
                "player_hand":   self.player_hand,
                "dealer_hand":   self.dealer_hand,
                "player_total":  hand_value(self.player_hand),
                "dealer_visible": self.dealer_hand[0] if self.dealer_hand else None,
                "status":        self.status,
            }
            self.on_ai_turn(state)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    game = BlackjackGame(root)

    # ── AI partner plugs in here ──────────────────────────────────────────────
    # Example (your partner replaces this with real AI logic):
    #
    # def my_ai(state):
    #     if state['player_total'] >= 17:
    #         game.ai_label.config(text="🤖 Suggest: Stand")
    #     else:
    #         game.ai_label.config(text="🤖 Suggest: Hit")
    #
    # game.on_ai_turn = my_ai
    # ─────────────────────────────────────────────────────────────────────────

    root.mainloop()