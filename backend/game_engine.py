
import random


# ── CARD VALUES ──────────────────────────────────────────────────────────────
# Face cards (J, Q, K) are all stored as 10.
# Aces are stored as 11 and reduced to 1 as needed when computing totals.

CARD_VALUES = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]  # one suit's worth
CARD_LABELS = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7", 8: "8", 9: "9", 10: "10", 11: "A",
}

NUM_DECKS      = 8
PENETRATION    = 0.81   # reshuffle when ~81% of shoe is dealt (≈ 6.5 / 8 decks)


# ── DECK ─────────────────────────────────────────────────────────────────────

def build_shoe(num_decks=NUM_DECKS):
    """Return a freshly shuffled shoe of num_decks standard decks."""
    shoe = CARD_VALUES * 4 * num_decks   # 4 suits × num_decks
    random.shuffle(shoe)
    return shoe


# ── HAND EVALUATION ──────────────────────────────────────────────────────────

def hand_total(cards):
    """
    Compute the best blackjack total for a list of card values.
    Aces start as 11 and are reduced to 1 as needed.
    Returns (total: int, is_soft: bool).
    """
    total = sum(cards)
    aces  = cards.count(11)
    while total > 21 and aces > 0:
        total -= 10
        aces  -= 1
    return total, aces > 0


def is_blackjack(cards):
    """True only if the hand is exactly [Ace, 10-value] (natural blackjack)."""
    return len(cards) == 2 and sum(cards) == 21


def is_bust(cards):
    """True if the hand total exceeds 21."""
    total, _ = hand_total(cards)
    return total > 21


def hand_label(cards):
    """
    Human-readable label for a hand, e.g. 'A + 7 = soft 18' or '10 + 6 = 16'.
    Used in API responses so the frontend can display it.
    """
    total, soft = hand_total(cards)
    card_str = " + ".join(CARD_LABELS[c] for c in cards)
    soft_str = "soft " if soft else ""
    if is_blackjack(cards):
        return f"{card_str} = Blackjack"
    if is_bust(cards):
        return f"{card_str} = bust ({total})"
    return f"{card_str} = {soft_str}{total}"


# ── GAME STATE ────────────────────────────────────────────────────────────────

class BlackjackGame:
    """
    Manages one complete blackjack session (multiple rounds, same shoe).

    State is kept as plain dicts/lists so it can be serialized to JSON
    and sent back to the frontend via Flask without any extra work.

    Usage:
        game = BlackjackGame()
        state = game.new_round(bet=10)
        state = game.player_action("hit")
        state = game.player_action("stand")
        # state always contains everything the frontend needs to render
    """

    def __init__(self):
        self.shoe          = build_shoe()
        self.cards_dealt   = 0
        self.round_active  = False
        self.player_hands  = []   # list of lists (multiple hands after split)
        self.active_hand   = 0    # index of the hand the player is acting on
        self.dealer_cards  = []
        self.bet           = 1
        self.balance       = 1000
        self.split_count   = 0    # how many times the player has split this round
        self.doubled       = []   # bool per hand — was this hand doubled?
        self.surrendered   = False
        self.can_surrender = True
        self.round_result  = None  # set when the round ends

    # ── SHOE MANAGEMENT ──────────────────────────────────────────────────────

    def _deal_card(self):
        """Deal one card from the shoe. Reshuffles if penetration reached."""
        if self.cards_dealt / len(self.shoe) >= PENETRATION:
            self.shoe        = build_shoe()
            self.cards_dealt = 0
        card = self.shoe[self.cards_dealt]
        self.cards_dealt += 1
        return card

    def _run_count(self):
        """
        Hi-Lo running count at the current point in the shoe.
        +1 for low cards (2–6), -1 for high cards (10, A), 0 for 7–9.
        Used as a feature when querying the AI model.
        """
        count = 0
        for card in self.shoe[:self.cards_dealt]:
            if card in (2, 3, 4, 5, 6):
                count += 1
            elif card in (10, 11):
                count -= 1
        return count

    # ── ROUND FLOW ───────────────────────────────────────────────────────────

    def new_round(self, bet=1):
        """
        Start a fresh round. Returns the initial game state dict.
        Raises ValueError if a round is already in progress.
        """
        if self.round_active:
            raise ValueError("A round is already in progress.")
        if bet > self.balance:
            raise ValueError("Bet exceeds current balance.")

        self.bet           = bet
        self.round_active  = True
        self.surrendered   = False
        self.can_surrender = True
        self.split_count   = 0
        self.round_result  = None

        # Deal: player, dealer, player, dealer (standard order)
        c1 = self._deal_card()
        d1 = self._deal_card()
        c2 = self._deal_card()
        d2 = self._deal_card()

        self.player_hands = [[c1, c2]]
        self.dealer_cards  = [d1, d2]
        self.active_hand   = 0
        self.doubled       = [False]

        # Check for immediate blackjack (dealer or player or both)
        state = self._build_state()
        if is_blackjack(self.dealer_cards) or is_blackjack(self.player_hands[0]):
            return self._end_round()

        return state

    def player_action(self, action):
        """
        Apply a player action to the current active hand.
        action: one of "hit", "stand", "double", "split", "surrender"
        Returns updated game state dict.
        Raises ValueError on illegal actions.
        """
        if not self.round_active:
            raise ValueError("No round in progress. Call new_round() first.")

        action = action.lower().strip()
        hand   = self.player_hands[self.active_hand]

        if action == "hit":
            hand.append(self._deal_card())
            self.can_surrender = False
            if is_bust(hand):
                return self._advance_or_end()
            return self._build_state()

        elif action == "stand":
            self.can_surrender = False
            return self._advance_or_end()

        elif action == "double":
            if len(hand) != 2:
                raise ValueError("Double down only allowed on first two cards.")
            if self.balance < self.bet * 2:
                raise ValueError("Insufficient balance to double down.")
            hand.append(self._deal_card())
            self.doubled[self.active_hand] = True
            self.can_surrender = False
            return self._advance_or_end()  # hand ends after double

        elif action == "split":
            if len(hand) != 2 or hand[0] != hand[1]:
                raise ValueError("Can only split a pair.")
            if self.split_count >= 3:
                raise ValueError("Maximum splits (3) reached.")
            if self.balance < self.bet * (self.split_count + 2):
                raise ValueError("Insufficient balance to split.")

            # Split: each card starts a new hand, each gets one new card
            card = hand[0]
            self.player_hands[self.active_hand] = [card, self._deal_card()]
            new_hand = [card, self._deal_card()]
            self.player_hands.insert(self.active_hand + 1, new_hand)
            self.doubled.insert(self.active_hand + 1, False)
            self.split_count += 1
            self.can_surrender = False

            # Aces get only one card after split — hand ends immediately
            if card == 11:
                return self._advance_or_end()

            return self._build_state()

        elif action == "surrender":
            if not self.can_surrender:
                raise ValueError("Surrender is only allowed on the first decision.")
            if self.split_count > 0:
                raise ValueError("Surrender not allowed after a split.")
            self.surrendered  = True
            self.round_active = False
            loss = self.bet / 2
            self.balance -= loss
            self.round_result = {
                "outcome": "surrender",
                "payout":  -loss,
                "message": f"Surrendered. Lost ${loss:.2f}.",
            }
            return self._build_state()

        else:
            raise ValueError(f"Unknown action: '{action}'. "
                             "Use hit / stand / double / split / surrender.")

    # ── INTERNAL HELPERS ─────────────────────────────────────────────────────

    def _advance_or_end(self):
        """
        Move to the next hand (after stand, bust, double, or split-ace end).
        If all hands are done, play the dealer hand and resolve.
        """
        self.active_hand += 1
        if self.active_hand >= len(self.player_hands):
            return self._end_round()
        return self._build_state()

    def _end_round(self):
        """
        Play out the dealer hand and resolve all player hands.
        Dealer hits on soft 17 (matching training data rules).
        """
        self.round_active = False

        # Dealer plays — only if at least one player hand hasn't busted
        player_all_bust = all(is_bust(h) for h in self.player_hands)
        dealer_bj       = is_blackjack(self.dealer_cards)

        if not player_all_bust and not dealer_bj and not self.surrendered:
            while True:
                total, soft = hand_total(self.dealer_cards)
                # Dealer hits on hard ≤16 OR soft 17
                if total < 17 or (total == 17 and soft):
                    self.dealer_cards.append(self._deal_card())
                else:
                    break

        dealer_total, _ = hand_total(self.dealer_cards)
        dealer_bj_flag  = is_blackjack(self.dealer_cards)

        # Resolve each player hand
        outcomes  = []
        net_total = 0.0

        for i, hand in enumerate(self.player_hands):
            p_total, _ = hand_total(hand)
            p_bj       = is_blackjack(hand) and self.split_count == 0
            doubled    = self.doubled[i]
            effective_bet = self.bet * (2 if doubled else 1)

            if self.surrendered:
                # Already resolved above
                outcome, payout = "surrender", -(self.bet / 2)

            elif p_bj and dealer_bj_flag:
                outcome, payout = "push", 0.0

            elif p_bj:
                payout  = effective_bet * 1.5
                outcome = "blackjack"

            elif dealer_bj_flag:
                payout  = -effective_bet
                outcome = "lose"

            elif is_bust(hand):
                payout  = -effective_bet
                outcome = "bust"

            elif is_bust(self.dealer_cards):
                payout  = effective_bet
                outcome = "win"

            elif p_total > dealer_total:
                payout  = effective_bet
                outcome = "win"

            elif p_total == dealer_total:
                payout  = 0.0
                outcome = "push"

            else:
                payout  = -effective_bet
                outcome = "lose"

            self.balance += payout
            net_total    += payout

            outcomes.append({
                "hand":    hand_label(hand),
                "outcome": outcome,
                "payout":  round(payout, 2),
            })

        self.round_result = {
            "outcomes":    outcomes,
            "net_payout":  round(net_total, 2),
            "dealer_hand": hand_label(self.dealer_cards),
        }

        return self._build_state()

    def _build_state(self):
        """
        Serialize the full game state to a plain dict for JSON response.
        This is what Flask returns to the frontend on every action.
        """
        active = self.player_hands[self.active_hand] if self.round_active else []
        p_total, p_soft = hand_total(active) if active else (0, False)
        active_can_split = (
            len(active) == 2
            and len(active) > 1
            and active[0] == active[1]
            and self.split_count < 3
        )

        return {
            # Round status
            "round_active":   self.round_active,
            "round_result":   self.round_result,

            # Player
            "player_hands":   [hand_label(h) for h in self.player_hands],
            "player_cards":   self.player_hands,       # raw values for AI query
            "active_hand":    self.active_hand,
            "balance":        round(self.balance, 2),
            "bet":            self.bet,

            # Dealer (second card hidden while round is active)
            "dealer_upcard":  self.dealer_cards[0] if self.dealer_cards else None,
            "dealer_hand":    hand_label(self.dealer_cards) if not self.round_active
                              else f"{CARD_LABELS[self.dealer_cards[0]]} + ?",

            # Available actions for the active hand
            "can_hit":        self.round_active and not is_bust(active),
            "can_stand":      self.round_active,
            "can_double":     self.round_active and len(active) == 2,
            "can_split":      self.round_active and active_can_split,
            "can_surrender":  self.round_active and self.can_surrender and self.split_count == 0,

            # AI query helpers
            "player_total":   p_total,
            "is_soft":        int(p_soft),
            "run_count":      self._run_count(),
        }