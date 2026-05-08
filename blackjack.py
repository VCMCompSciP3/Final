import tkinter as tk
import random
import json
import os

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

def card_rank_value(rank):
    if rank in ('J', 'Q', 'K'):
        return 10
    if rank == 'A':
        return 11
    return int(rank)

# ─── CHIP CONFIG ─────────────────────────────────────────────────────────────

CHIPS = [
    {"value": 1,   "color": "#ffffff", "text_color": "#1a1a1a", "label": "$1"},
    {"value": 5,   "color": "#c0392b", "text_color": "#ffffff", "label": "$5"},
    {"value": 25,  "color": "#2471a3", "text_color": "#ffffff", "label": "$25"},
    {"value": 100, "color": "#1e4d35", "text_color": "#c9a84c", "label": "$100"},
    {"value": 500, "color": "#1a1a1a", "text_color": "#c9a84c", "label": "$500"},
]

STARTING_BALANCE = 1000

# ─── LEADERBOARD ─────────────────────────────────────────────────────────────

LEADERBOARD_FILE = "leaderboard.json"
MAX_LEADERBOARD = 10

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return []

def save_leaderboard(board):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(board, f, indent=2)

def update_leaderboard(username, score):
    board = load_leaderboard()
    # Check if player already exists — update if score is higher
    for entry in board:
        if entry["name"].lower() == username.lower():
            if score > entry["score"]:
                entry["score"] = score
            board.sort(key=lambda x: x["score"], reverse=True)
            board = board[:MAX_LEADERBOARD]
            save_leaderboard(board)
            return board
    # New player
    board.append({"name": username, "score": score})
    board.sort(key=lambda x: x["score"], reverse=True)
    board = board[:MAX_LEADERBOARD]
    save_leaderboard(board)
    return board

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
        self.status = "idle"           # idle | playing | split | dealer | ended
        self.balance = STARTING_BALANCE
        self.current_bet = 0
        self.username = ""
        self.peak_balance = STARTING_BALANCE  # track highest balance reached

        # Split state
        self.split_hands = []          # list of two hands when split
        self.split_bets = []           # bet for each split hand
        self.active_split = 0          # which split hand is being played (0 or 1)
        self.split_results = []        # result for each hand
        self.is_split = False

        self._build_ui()
        self._render()
        self.root.after(100, self._show_username_screen)

    # ── USERNAME SCREEN ───────────────────────────────────────────────────────

    def _show_username_screen(self):
        self.username_win = tk.Toplevel(self.root)
        self.username_win.title("Welcome")
        self.username_win.configure(bg="#1e4d35")
        self.username_win.resizable(False, False)
        self.username_win.grab_set()  # block main window until name entered

        # Center it over the main window
        self.root.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width() // 2 - 200
        y = self.root.winfo_y() + self.root.winfo_height() // 2 - 120
        self.username_win.geometry(f"400x240+{x}+{y}")

        tk.Label(
            self.username_win, text="👑 King of Blackjack",
            font=("Georgia", 18, "bold"), bg="#1e4d35", fg="#c9a84c"
        ).pack(pady=(24, 4))

        tk.Label(
            self.username_win, text="Enter your username to play:",
            font=("Georgia", 11), bg="#1e4d35", fg="#f0ead8"
        ).pack(pady=(0, 10))

        self.username_entry = tk.Entry(
            self.username_win,
            font=("Georgia", 13), width=20,
            bg="#163828", fg="#e8c97a",
            insertbackground="#e8c97a",
            relief="flat", justify="center"
        )
        self.username_entry.pack(ipady=6)
        self.username_entry.focus()
        self.username_entry.bind("<Return>", lambda e: self._submit_username())

        tk.Button(
            self.username_win, text="Let's Play!",
            font=("Georgia", 12, "bold"),
            bg="#c9a84c", fg="#1a3a2a",
            activebackground="#e8c97a", activeforeground="#1a3a2a",
            relief="flat", cursor="hand2", bd=0,
            width=12, pady=6,
            command=self._submit_username
        ).pack(pady=14)

    def _submit_username(self):
        name = self.username_entry.get().strip()
        if not name:
            self.username_entry.config(bg="#4a1a1a")
            return
        self.username = name
        self.username_win.destroy()
        self.root.title(f"Blackjack — {self.username}")

    # ── LEADERBOARD WINDOW ────────────────────────────────────────────────────

    def _show_leaderboard(self):
        board = load_leaderboard()

        win = tk.Toplevel(self.root)
        win.title("Leaderboard")
        win.configure(bg="#1e4d35")
        win.resizable(False, False)

        x = self.root.winfo_x() + self.root.winfo_width() + 10
        y = self.root.winfo_y()
        win.geometry(f"320x420+{x}+{y}")

        tk.Label(
            win, text="👑 King of Blackjack",
            font=("Georgia", 15, "bold"), bg="#1e4d35", fg="#c9a84c"
        ).pack(pady=(18, 2))

        tk.Label(
            win, text="Leaderboard",
            font=("Georgia", 11), bg="#1e4d35", fg="#a8c4b0"
        ).pack(pady=(0, 10))

        tk.Frame(win, bg="#c9a84c", height=1, width=280).pack(pady=4)

        if not board:
            tk.Label(
                win, text="No scores yet!\nBe the first to make the board.",
                font=("Georgia", 11), bg="#1e4d35", fg="#f0ead8",
                justify="center"
            ).pack(pady=20)
        else:
            medals = ["🥇", "🥈", "🥉"]
            for i, entry in enumerate(board):
                row = tk.Frame(win, bg="#163828" if i % 2 == 0 else "#1e4d35")
                row.pack(fill="x", padx=20, pady=2, ipady=4)

                medal = medals[i] if i < 3 else f"#{i+1}"
                tk.Label(
                    row, text=medal,
                    font=("Georgia", 12), bg=row["bg"], fg="#c9a84c", width=4
                ).pack(side="left")

                tk.Label(
                    row, text=entry["name"],
                    font=("Georgia", 11, "bold"), bg=row["bg"], fg="#f0ead8",
                    anchor="w", width=14
                ).pack(side="left")

                tk.Label(
                    row, text=f"${entry['score']}",
                    font=("Georgia", 11), bg=row["bg"], fg="#e8c97a",
                    anchor="e"
                ).pack(side="right", padx=8)

        tk.Frame(win, bg="#c9a84c", height=1, width=280).pack(pady=10)

        tk.Button(
            win, text="Close",
            font=("Georgia", 10), width=10,
            bg="#245c3e", fg="#f0ead8",
            activebackground="#2e7a50", activeforeground="#f0ead8",
            relief="flat", cursor="hand2", bd=0,
            command=win.destroy
        ).pack(pady=(0, 16))

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):

        # Title
        tk.Label(
            self.root, text="BLACKJACK",
            font=("Georgia", 26, "bold"),
            bg="#1e4d35", fg="#c9a84c"
        ).pack(pady=(20, 2))

        # Balance & bet bar
        info_frame = tk.Frame(self.root, bg="#163828")
        info_frame.pack(fill="x", padx=0, pady=0, ipadx=10, ipady=6)

        self.balance_label = tk.Label(
            info_frame, text=f"Balance: ${self.balance}",
            font=("Georgia", 12, "bold"), bg="#163828", fg="#c9a84c"
        )
        self.balance_label.pack(side="left", padx=20)

        self.bet_label = tk.Label(
            info_frame, text="Bet: $0",
            font=("Georgia", 12, "bold"), bg="#163828", fg="#e8c97a"
        )
        self.bet_label.pack(side="right", padx=20)

        # Dealer section
        tk.Label(
            self.root, text="DEALER",
            font=("Georgia", 11), bg="#1e4d35", fg="#a8c4b0"
        ).pack(pady=(12, 0))

        self.dealer_score_label = tk.Label(
            self.root, text="",
            font=("Georgia", 13, "bold"), bg="#1e4d35", fg="#f0ead8"
        )
        self.dealer_score_label.pack()

        self.dealer_frame = tk.Frame(self.root, bg="#1e4d35", height=100)
        self.dealer_frame.pack(pady=6)

        # Divider
        tk.Frame(self.root, bg="#c9a84c", height=1, width=560).pack(pady=6)

        # Player section — holds either normal hand or split hands side by side
        tk.Label(
            self.root, text="YOU",
            font=("Georgia", 11), bg="#1e4d35", fg="#a8c4b0"
        ).pack()

        self.player_score_label = tk.Label(
            self.root, text="",
            font=("Georgia", 13, "bold"), bg="#1e4d35", fg="#f0ead8"
        )
        self.player_score_label.pack()

        # Outer frame holds normal hand or split columns
        self.player_area = tk.Frame(self.root, bg="#1e4d35")
        self.player_area.pack(pady=6)

        # Normal single hand frame
        self.player_frame = tk.Frame(self.player_area, bg="#1e4d35", height=100)
        self.player_frame.pack(side="left")

        # Split hand frames (hidden until split)
        self.split_outer = tk.Frame(self.player_area, bg="#1e4d35")
        # Left split hand
        self.split_frame_0 = tk.Frame(self.split_outer, bg="#1e4d35", bd=2, relief="flat")
        self.split_frame_0.pack(side="left", padx=12)
        self.split_label_0 = tk.Label(
            self.split_frame_0, text="Hand 1",
            font=("Georgia", 10, "bold"), bg="#1e4d35", fg="#c9a84c"
        )
        self.split_label_0.pack()
        self.split_cards_0 = tk.Frame(self.split_frame_0, bg="#1e4d35", height=100)
        self.split_cards_0.pack()
        self.split_score_0 = tk.Label(
            self.split_frame_0, text="",
            font=("Georgia", 11), bg="#1e4d35", fg="#f0ead8"
        )
        self.split_score_0.pack()

        # Right split hand
        self.split_frame_1 = tk.Frame(self.split_outer, bg="#1e4d35", bd=2, relief="flat")
        self.split_frame_1.pack(side="left", padx=12)
        self.split_label_1 = tk.Label(
            self.split_frame_1, text="Hand 2",
            font=("Georgia", 10, "bold"), bg="#1e4d35", fg="#a8c4b0"
        )
        self.split_label_1.pack()
        self.split_cards_1 = tk.Frame(self.split_frame_1, bg="#1e4d35", height=100)
        self.split_cards_1.pack()
        self.split_score_1 = tk.Label(
            self.split_frame_1, text="",
            font=("Georgia", 11), bg="#1e4d35", fg="#f0ead8"
        )
        self.split_score_1.pack()

        # Message
        self.message_label = tk.Label(
            self.root, text="Place your bet to start!",
            font=("Georgia", 13, "bold"), bg="#1e4d35", fg="#e8c97a",
            height=2, wraplength=520
        )
        self.message_label.pack()

        # ── CHIP BUTTONS ──────────────────────────────────────────────────────
        tk.Label(
            self.root, text="PLACE BET",
            font=("Georgia", 9), bg="#1e4d35", fg="#a8c4b0"
        ).pack()

        self.chip_frame = tk.Frame(self.root, bg="#1e4d35")
        self.chip_frame.pack(pady=6)

        self.chip_buttons = []
        for chip in CHIPS:
            btn = tk.Canvas(
                self.chip_frame,
                width=54, height=54,
                bg="#1e4d35", highlightthickness=0,
                cursor="hand2"
            )
            btn.pack(side="left", padx=6)
            self._draw_chip(btn, chip)
            btn.bind("<Button-1>", lambda e, v=chip["value"]: self._place_chip(v))
            self.chip_buttons.append(btn)

        # Clear bet button
        self.btn_clear = tk.Button(
            self.root, text="Clear Bet",
            font=("Georgia", 10), width=10,
            bg="#7a2020", fg="#f0ead8",
            activebackground="#a02020", activeforeground="#f0ead8",
            relief="flat", cursor="hand2", bd=0,
            command=self._clear_bet
        )
        self.btn_clear.pack(pady=(2, 6))

        # ── GAME BUTTONS ──────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg="#1e4d35")
        btn_frame.pack(pady=6)

        btn_style = dict(
            font=("Georgia", 12, "bold"),
            width=8, height=1,
            relief="flat", cursor="hand2", bd=0
        )

        self.btn_deal = tk.Button(
            btn_frame, text="Deal",
            bg="#c9a84c", fg="#1a3a2a",
            activebackground="#e8c97a", activeforeground="#1a3a2a",
            command=self.deal, **btn_style
        )
        self.btn_deal.grid(row=0, column=0, padx=6)

        self.btn_hit = tk.Button(
            btn_frame, text="Hit",
            bg="#245c3e", fg="#f0ead8",
            activebackground="#2e7a50", activeforeground="#f0ead8",
            command=self.hit, **btn_style
        )
        self.btn_hit.grid(row=0, column=1, padx=6)

        self.btn_stand = tk.Button(
            btn_frame, text="Stand",
            bg="#245c3e", fg="#f0ead8",
            activebackground="#2e7a50", activeforeground="#f0ead8",
            command=self.stand, **btn_style
        )
        self.btn_stand.grid(row=0, column=2, padx=6)

        self.btn_split = tk.Button(
            btn_frame, text="Split",
            bg="#7a3a8a", fg="#f0ead8",
            activebackground="#9a4aaa", activeforeground="#f0ead8",
            command=self.split, **btn_style
        )
        self.btn_split.grid(row=0, column=3, padx=6)

        # Bind R key to reset
        self.root.bind("<r>", lambda e: self.reset())
        self.root.bind("<R>", lambda e: self.reset())

        # Leaderboard button
        tk.Button(
            self.root, text="👑 View Leaderboard",
            font=("Georgia", 10, "bold"),
            bg="#163828", fg="#c9a84c",
            activebackground="#1e4d35", activeforeground="#e8c97a",
            relief="flat", cursor="hand2", bd=0,
            command=self._show_leaderboard
        ).pack(pady=(6, 0))

        # AI suggestion box
        tk.Label(
            self.root, text="AI ASSISTANT",
            font=("Georgia", 9), bg="#1e4d35", fg="#a8c4b0"
        ).pack(pady=(10, 0))

        self.ai_label = tk.Label(
            self.root,
            text="🤖 AI assistant ready...",
            font=("Georgia", 11, "italic"),
            bg="#163828", fg="#a8c4b0",
            width=52, height=2,
            relief="flat", wraplength=460
        )
        self.ai_label.pack(pady=(4, 16))

    # ── CHIP DRAWING ──────────────────────────────────────────────────────────

    def _draw_chip(self, canvas, chip):
        canvas.create_oval(3, 3, 51, 51, fill=chip["color"], outline="#c9a84c", width=3)
        canvas.create_oval(9, 9, 45, 45, fill="", outline=chip["text_color"], width=1, dash=(3, 3))
        canvas.create_text(27, 27, text=chip["label"],
                           font=("Georgia", 9, "bold"), fill=chip["text_color"])

    # ── BETTING ───────────────────────────────────────────────────────────────

    def _place_chip(self, value):
        if self.status not in ("idle", "ended"):
            return
        if self.current_bet + value > self.balance:
            self.message_label.config(text="❌ Not enough balance!")
            return
        self.current_bet += value
        self._update_bet_display()

    def _clear_bet(self):
        if self.status in ("playing", "dealer", "split"):
            return
        self.current_bet = 0
        self._update_bet_display()
        self.message_label.config(text="Place your bet to start!")

    def _update_bet_display(self):
        self.bet_label.config(text=f"Bet: ${self.current_bet}")
        self.balance_label.config(text=f"Balance: ${self.balance}")

    # ── CARD WIDGET ───────────────────────────────────────────────────────────

    def _card_widget(self, parent, card, face_down=False, highlight=False):
        frame = tk.Frame(
            parent,
            bg="#fdfaf4", width=64, height=92,
            relief="raised", bd=2 if highlight else 1
        )
        frame.pack_propagate(False)

        if face_down:
            tk.Label(
                frame, text="",
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

    # ── CAN SPLIT CHECK ───────────────────────────────────────────────────────

    def _can_split(self):
        if self.status != "playing" or self.is_split:
            return False
        if len(self.player_hand) != 2:
            return False
        r1 = self.player_hand[0]['rank']
        r2 = self.player_hand[1]['rank']
        # Same rank, or both worth 10
        return r1 == r2 or (card_rank_value(r1) == 10 and card_rank_value(r2) == 10)

    # ── RENDER ────────────────────────────────────────────────────────────────

    def _render(self):
        is_ended = self.status == "ended"

        # Clear dealer cards
        for widget in self.dealer_frame.winfo_children():
            widget.destroy()

        for i, card in enumerate(self.dealer_hand):
            face_down = (i == 1 and not is_ended)
            w = self._card_widget(self.dealer_frame, card, face_down)
            w.pack(side="left", padx=4)

        # Dealer score
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

        # ── Split mode rendering ──
        if self.is_split:
            self.player_frame.pack_forget()
            self.split_outer.pack(side="left")

            for hand_idx, (cards_frame, score_lbl, hand_lbl) in enumerate([
                (self.split_cards_0, self.split_score_0, self.split_label_0),
                (self.split_cards_1, self.split_score_1, self.split_label_1),
            ]):
                for widget in cards_frame.winfo_children():
                    widget.destroy()

                hand = self.split_hands[hand_idx]
                is_active = (hand_idx == self.active_split) and self.status == "split"

                # Highlight active hand
                border_color = "#c9a84c" if is_active else "#1e4d35"
                self.split_frame_0.config(highlightbackground=border_color, highlightthickness=2) if hand_idx == 0 else \
                self.split_frame_1.config(highlightbackground=border_color, highlightthickness=2)

                hand_lbl.config(fg="#c9a84c" if is_active else "#a8c4b0")

                for card in hand:
                    w = self._card_widget(cards_frame, card)
                    w.pack(side="left", padx=3)

                result_tag = ""
                if is_ended and hand_idx < len(self.split_results):
                    result_tag = f" {self.split_results[hand_idx]}"

                score_lbl.config(text=f"{hand_value(hand)}{result_tag}")

            self.player_score_label.config(
                text=f"Hand 1: {hand_value(self.split_hands[0])}   |   Hand 2: {hand_value(self.split_hands[1])}"
                if len(self.split_hands) == 2 else ""
            )

        else:
            # Normal single hand
            self.split_outer.pack_forget()
            self.player_frame.pack(side="left")

            for widget in self.player_frame.winfo_children():
                widget.destroy()

            for card in self.player_hand:
                w = self._card_widget(self.player_frame, card)
                w.pack(side="left", padx=4)

            if self.player_hand:
                self.player_score_label.config(text=f"You: {hand_value(self.player_hand)}")
            else:
                self.player_score_label.config(text="")

        # ── Button states ──
        playing = self.status in ("playing", "split")
        idle_or_ended = self.status in ("idle", "ended")
        can_split = self._can_split()

        self.btn_deal.config(
            state="normal" if idle_or_ended else "disabled",
            bg="#c9a84c" if idle_or_ended else "#7a6530"
        )
        self.btn_hit.config(
            state="normal" if playing else "disabled",
            bg="#245c3e" if playing else "#1a3a2a"
        )
        self.btn_stand.config(
            state="normal" if playing else "disabled",
            bg="#245c3e" if playing else "#1a3a2a"
        )
        self.btn_split.config(
            state="normal" if can_split else "disabled",
            bg="#7a3a8a" if can_split else "#3a1a4a"
        )
        self.btn_clear.config(
            state="normal" if idle_or_ended else "disabled"
        )

        self._update_bet_display()

        if self.balance <= 0 and self.current_bet == 0 and self.status == "ended":
            self.message_label.config(text="💸 You're broke! Press R to reset your balance.")

    # ── ACTIONS ───────────────────────────────────────────────────────────────

    def deal(self):
        if self.current_bet == 0:
            self.message_label.config(text="⚠️ Place a bet first!")
            return

        self.balance -= self.current_bet
        self.is_split = False
        self.split_hands = []
        self.split_bets = []
        self.split_results = []
        self.active_split = 0

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
        if self.status == "playing" and not self.is_split:
            self.player_hand.append(self.deck.pop())
            total = hand_value(self.player_hand)
            self._render()
            self._notify_ai("hit")
            if total > 21:
                self._end_round("bust")
            elif total == 21:
                self.stand()

        elif self.status == "split":
            self.split_hands[self.active_split].append(self.deck.pop())
            total = hand_value(self.split_hands[self.active_split])
            self._render()
            if total > 21:
                self._resolve_split_hand("bust")
            elif total == 21:
                self._next_split_hand()

    def stand(self):
        if self.status == "playing" and not self.is_split:
            self.status = "dealer"
            self._render()
            self._run_dealer()
        elif self.status == "split":
            self._next_split_hand()

    # ── SPLIT ─────────────────────────────────────────────────────────────────

    def split(self):
        if not self._can_split():
            return
        if self.current_bet > self.balance:
            self.message_label.config(text="❌ Not enough balance to split!")
            return

        # Deduct second bet
        self.balance -= self.current_bet

        # Build two hands, each with one card + a new card
        card1 = self.player_hand[0]
        card2 = self.player_hand[1]
        self.split_hands = [
            [card1, self.deck.pop()],
            [card2, self.deck.pop()],
        ]
        self.split_bets = [self.current_bet, self.current_bet]
        self.is_split = True
        self.active_split = 0
        self.status = "split"
        self.split_results = []

        self.message_label.config(text="✂️ Hand split! Playing Hand 1...")
        self._render()

    def _next_split_hand(self):
        if self.active_split == 0:
            self.active_split = 1
            self.message_label.config(text="Now playing Hand 2...")
            self._render()
        else:
            # Both hands done — run dealer
            self.status = "dealer"
            self._render()
            self._run_dealer()

    def _resolve_split_hand(self, result):
        # Called when a split hand busts
        bust_msg = f"Hand {self.active_split + 1} busted!"
        self.split_results.append("💥")
        self.message_label.config(text=bust_msg)
        self._next_split_hand()

    # ── DEALER ────────────────────────────────────────────────────────────────

    def _run_dealer(self):
        if hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
            self._render()
            self.root.after(600, self._run_dealer)
        else:
            self._determine_winner()

    def _determine_winner(self):
        if self.is_split:
            self._determine_split_winner()
        else:
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

    def _determine_split_winner(self):
        d = hand_value(self.dealer_hand)
        total_winnings = 0
        messages = []
        self.split_results = []

        for i, hand in enumerate(self.split_hands):
            p = hand_value(hand)
            bet = self.split_bets[i]

            # Check if this hand already busted
            if p > 21:
                messages.append(f"Hand {i+1}: 💥 Bust  -${bet}")
                self.split_results.append("💥 Bust")
                continue

            if d > 21 or p > d:
                total_winnings += bet * 2
                messages.append(f"Hand {i+1}: ✅ Win  +${bet}")
                self.split_results.append("✅ Win")
            elif p == d:
                total_winnings += bet
                messages.append(f"Hand {i+1}: 🤝 Push")
                self.split_results.append("🤝 Push")
            else:
                messages.append(f"Hand {i+1}: ❌ Lose  -${bet}")
                self.split_results.append("❌ Lose")

        self.balance += total_winnings
        self.peak_balance = max(self.peak_balance, self.balance)
        self.status = "ended"
        self.message_label.config(text="   |   ".join(messages) + "   (Press R to play again)")

        # Save to leaderboard using peak balance
        if self.username:
            update_leaderboard(self.username, self.peak_balance)

        self._render()
        self._notify_ai("end", "split")

    def _end_round(self, result):
        self.status = "ended"

        messages = {
            "blackjack":   "🃏 Blackjack! You win!  (Press R to play again)",
            "bust":        "💥 Bust! You went over 21.  (Press R to play again)",
            "dealer-bust": "🎉 Dealer busted! You win!  (Press R to play again)",
            "win":         "✅ You win!  (Press R to play again)",
            "lose":        "❌ Dealer wins.  (Press R to play again)",
            "push":        "🤝 It's a tie — bet returned!  (Press R to play again)",
        }

        if result in ("win", "dealer-bust"):
            winnings = self.current_bet * 2
            self.balance += winnings
            self.peak_balance = max(self.peak_balance, self.balance)
            self.message_label.config(text=f"{messages[result]}  +${self.current_bet}")
        elif result == "blackjack":
            winnings = int(self.current_bet * 2.5)
            self.balance += winnings
            self.peak_balance = max(self.peak_balance, self.balance)
            self.message_label.config(text=f"{messages[result]}  +${winnings - self.current_bet}")
        elif result == "push":
            self.balance += self.current_bet
            self.message_label.config(text=messages[result])
        else:
            self.message_label.config(text=f"{messages.get(result, '')}  -${self.current_bet}")

        self.current_bet = 0

        # Save to leaderboard using peak balance
        if self.username:
            update_leaderboard(self.username, self.peak_balance)

        self._render()
        self._notify_ai("end", result)

    # ── RESET ─────────────────────────────────────────────────────────────────

    def reset(self):
        # Only allow reset when a round has ended or game is idle
        if self.status not in ("ended", "idle"):
            return

        # Clear all game state
        self.deck = []
        self.player_hand = []
        self.dealer_hand = []
        self.status = "idle"
        self.balance = STARTING_BALANCE
        self.peak_balance = STARTING_BALANCE
        self.current_bet = 0
        self.username = ""
        self.is_split = False
        self.split_hands = []
        self.split_bets = []
        self.split_results = []
        self.active_split = 0

        # Clear the board visually
        self.message_label.config(text="Place your bet to start!")
        self.ai_label.config(text="🤖 AI assistant ready...")
        self.root.title("Blackjack")
        self._render()

        # Send player back to username screen
        self._show_username_screen()

    # ── AI HOOK ───────────────────────────────────────────────────────────────

    def _notify_ai(self, event, data=None):
        if hasattr(self, 'on_ai_turn') and callable(self.on_ai_turn):
            state = {
                "event":          event,
                "data":           data,
                "player_hand":    self.player_hand,
                "dealer_hand":    self.dealer_hand,
                "player_total":   hand_value(self.player_hand),
                "dealer_visible": self.dealer_hand[0] if self.dealer_hand else None,
                "status":         self.status,
                "balance":        self.balance,
                "current_bet":    self.current_bet,
                "is_split":       self.is_split,
                "split_hands":    self.split_hands,
                "active_split":   self.active_split,
            }
            self.on_ai_turn(state)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    game = BlackjackGame(root)

    # ── AI partner plugs in here ──────────────────────────────────────────────
    # def my_ai(state):
    #     if state['player_total'] >= 17:
    #         game.ai_label.config(text="🤖 Suggest: Stand")
    #     else:
    #         game.ai_label.config(text="🤖 Suggest: Hit")
    # game.on_ai_turn = my_ai
    # ─────────────────────────────────────────────────────────────────────────

    root.mainloop()