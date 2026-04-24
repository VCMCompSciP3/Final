// ─── DECK ───────────────────────────────────────────────────────────────────

const SUITS = ['♠', '♥', '♦', '♣'];
const RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'];

function createDeck() {
  const deck = [];
  for (const suit of SUITS) {
    for (const rank of RANKS) {
      deck.push({ suit, rank });
    }
  }
  return deck;
}

function shuffle(deck) {
  for (let i = deck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [deck[i], deck[j]] = [deck[j], deck[i]];
  }
  return deck;
}

// ─── HAND VALUE ──────────────────────────────────────────────────────────────

function cardValue(rank) {
  if (['J', 'Q', 'K'].includes(rank)) return 10;
  if (rank === 'A') return 11; // handled separately below
  return parseInt(rank);
}

function handValue(hand) {
  let total = 0;
  let aces = 0;

  for (const card of hand) {
    if (card.rank === 'A') {
      aces++;
      total += 11;
    } else {
      total += cardValue(card.rank);
    }
  }

  // Reduce aces from 11 → 1 as needed to avoid bust
  while (total > 21 && aces > 0) {
    total -= 10;
    aces--;
  }

  return total;
}

// ─── GAME STATE ──────────────────────────────────────────────────────────────

let gameState = {
  deck: [],
  playerHand: [],
  dealerHand: [],
  status: 'idle', // 'idle' | 'playing' | 'dealer' | 'ended'
  message: '',
  playerScore: 0,
  dealerScore: 0,
};

// ─── GAME ACTIONS ────────────────────────────────────────────────────────────

function dealGame() {
  gameState.deck = shuffle(createDeck());
  gameState.playerHand = [gameState.deck.pop(), gameState.deck.pop()];
  gameState.dealerHand = [gameState.deck.pop(), gameState.deck.pop()];
  gameState.status = 'playing';
  gameState.message = '';

  // Check for immediate blackjack
  if (handValue(gameState.playerHand) === 21) {
    endRound('blackjack');
    return;
  }

  render();

  // Let AI partner hook in here
  notifyAI('deal');
}

function hit() {
  if (gameState.status !== 'playing') return;

  gameState.playerHand.push(gameState.deck.pop());
  const value = handValue(gameState.playerHand);

  if (value > 21) {
    endRound('bust');
  } else if (value === 21) {
    stand(); // auto-stand on 21
  } else {
    render();
    notifyAI('hit');
  }
}

function stand() {
  if (gameState.status !== 'playing') return;
  gameState.status = 'dealer';
  render();
  runDealer();
}

function runDealer() {
  // Dealer draws until 17+
  const dealerInterval = setInterval(() => {
    if (handValue(gameState.dealerHand) < 17) {
      gameState.dealerHand.push(gameState.deck.pop());
      render();
    } else {
      clearInterval(dealerInterval);
      determineWinner();
    }
  }, 600);
}

function determineWinner() {
  const playerTotal = handValue(gameState.playerHand);
  const dealerTotal = handValue(gameState.dealerHand);

  if (dealerTotal > 21) {
    endRound('dealer-bust');
  } else if (playerTotal > dealerTotal) {
    endRound('win');
  } else if (dealerTotal > playerTotal) {
    endRound('lose');
  } else {
    endRound('push');
  }
}

function endRound(result) {
  gameState.status = 'ended';

  const messages = {
    blackjack: '🃏 Blackjack! You win!',
    bust: '💥 Bust! You went over 21.',
    'dealer-bust': '🎉 Dealer busted! You win!',
    win: '✅ You win!',
    lose: '❌ Dealer wins.',
    push: '🤝 Push — it\'s a tie.',
  };

  gameState.message = messages[result] || '';
  render();
  notifyAI('end', result);
}

// ─── AI HOOK ─────────────────────────────────────────────────────────────────
// Your partner will fill this in. It receives the current game state
// and the event that triggered it ('deal', 'hit', 'end', etc.)

function notifyAI(event, data) {
  if (typeof window.onAITurn === 'function') {
    window.onAITurn({
      event,
      data,
      playerHand: gameState.playerHand,
      dealerHand: gameState.dealerHand,
      playerTotal: handValue(gameState.playerHand),
      dealerVisible: gameState.dealerHand[0], // only first card is face-up
      status: gameState.status,
    });
  }
}

// ─── RENDER ──────────────────────────────────────────────────────────────────

function cardHTML(card, faceDown = false) {
  if (faceDown) {
    return `<div class="card face-down">🂠</div>`;
  }
  const isRed = card.suit === '♥' || card.suit === '♦';
  return `<div class="card ${isRed ? 'red' : ''}">
    <span class="rank">${card.rank}</span>
    <span class="suit">${card.suit}</span>
  </div>`;
}

function render() {
  const isEnded = gameState.status === 'ended' || gameState.status === 'dealer';

  // Dealer hand — hide second card until round ends
  document.getElementById('dealer-cards').innerHTML =
    gameState.dealerHand
      .map((card, i) => cardHTML(card, i === 1 && !isEnded))
      .join('');

  const dealerTotal = isEnded
    ? handValue(gameState.dealerHand)
    : cardValue(gameState.dealerHand[0].rank) === 11 ? 11 : cardValue(gameState.dealerHand[0].rank);

  document.getElementById('dealer-score').textContent =
    isEnded ? `Dealer: ${handValue(gameState.dealerHand)}` : `Dealer: ${dealerTotal}+`;

  // Player hand
  document.getElementById('player-cards').innerHTML =
    gameState.playerHand.map(card => cardHTML(card)).join('');
  document.getElementById('player-score').textContent =
    `You: ${handValue(gameState.playerHand)}`;

  // Buttons
  const playing = gameState.status === 'playing';
  document.getElementById('btn-hit').disabled = !playing;
  document.getElementById('btn-stand').disabled = !playing;
  document.getElementById('btn-deal').disabled = gameState.status === 'playing' || gameState.status === 'dealer';

  // Message
  document.getElementById('message').textContent = gameState.message;

  // AI suggestion area (your partner will populate this)
  const aiBox = document.getElementById('ai-suggestion');
  if (aiBox && gameState.status !== 'playing') {
    aiBox.textContent = '';
  }
}

// ─── INIT ────────────────────────────────────────────────────────────────────

document.getElementById('btn-deal').addEventListener('click', dealGame);
document.getElementById('btn-hit').addEventListener('click', hit);
document.getElementById('btn-stand').addEventListener('click', stand);

// Initial render
render();