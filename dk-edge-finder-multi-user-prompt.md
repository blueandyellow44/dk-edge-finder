# DK Edge Finder — Multi-User Full-Stack App

## What This Is

Build a multi-user version of the DK Edge Finder. Currently it's a static site (`index.html` + `data.json`) deployed on Netlify that shows one user's bankroll and bets. The goal is to turn it into a full-stack app where multiple users each get their own bankroll tracking, bet history, and Kelly sizing — all powered by a single shared daily edge scan.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React SPA on Netlify)                        │
│  - Login / signup (Firebase Auth)                       │
│  - Shared picks dashboard (same for everyone)           │
│  - Personal bankroll & bet tracking (per user)          │
│  - Kelly sizing calculated from user's own bankroll     │
└──────────────────────┬──────────────────────────────────┘
                       │ Firebase SDK calls (no backend needed)
┌──────────────────────▼──────────────────────────────────┐
│  Firebase (Google Cloud — free Spark plan)               │
│  - Firebase Auth (email/password + Google sign-in)      │
│  - Cloud Firestore (NoSQL database)                     │
│  - Cloud Functions (daily scan cron at 6 AM PT)         │
└─────────────────────────────────────────────────────────┘
```

No separate backend server needed. The React frontend talks directly to Firebase using the client SDK, and Firestore Security Rules enforce that users can only access their own data.

## Existing Code Reference

The current working single-user version lives at: https://github.com/blueandyellow44/dk-edge-finder.git

Key files to reference for the data model and UI:

### Current `data.json` schema (becomes the shared picks + per-user overlay)
```json
{
  "scan_date": "2026-03-16",
  "scan_subtitle": "Monday, March 16, 2026 — NBA, NHL",
  "bankroll": {
    "current": 550.23,
    "starting": 500.00,
    "profit": 50.23,
    "record": { "wins": 1, "losses": 0, "pushes": 0 },
    "pending_count": 1,
    "pending_label": "Suns +8.5 — $18.37"
  },
  "games_analyzed": 10,
  "best_bet": {
    "title": "Suns +8.5 (-110) — 7.6% Edge (High Tier)",
    "desc": "Multiple models flag PHX spread value."
  },
  "picks": [
    {
      "rank": 1,
      "sport": "NBA",
      "event": "Suns @ Celtics",
      "market": "Spread",
      "pick": "Suns +8.5",
      "odds": "-110",
      "implied": "52.4%",
      "model": "60.0%",
      "edge": 7.6,
      "tier": "High",
      "bet": "$18.37",
      "notes": "Dimers gives PHX 53% to cover...",
      "sources": "Dimers, BetMGM, Covers, OddsShark"
    }
  ],
  "bets": [
    {
      "date": "2026-03-16",
      "sport": "NBA",
      "event": "Suns @ Celtics",
      "pick": "Suns +8.5",
      "odds": "-110",
      "decimal_odds": 1.909,
      "edge": "7.6%",
      "wager": 18.37,
      "outcome": "pending"
    }
  ]
}
```

### Current `bankroll.json` schema (becomes per-user in Firestore)
```json
{
  "current_bankroll": 550.23,
  "starting_bankroll": 500.00,
  "last_updated": "2026-03-16T17:30:00-07:00",
  "lifetime_bets": 2,
  "lifetime_wins": 1,
  "lifetime_losses": 0,
  "lifetime_pushes": 0,
  "lifetime_profit": 50.23,
  "roi_pct": 0.00,
  "pending_bets": [
    {
      "id": "phx-spread-20260316",
      "date": "2026-03-16",
      "sport": "nba",
      "event": "Suns @ Celtics",
      "market": "spread",
      "pick": "Suns +8.5",
      "odds": -110,
      "decimal_odds": 1.909,
      "model_prob": 0.60,
      "edge_pct": 7.6,
      "tier": "High",
      "bet_size": 18.37,
      "outcome": null
    }
  ],
  "resolved_bets": [
    {
      "id": "phi-ml-20260315",
      "date": "2026-03-15",
      "sport": "nba",
      "event": "Trail Blazers @ 76ers",
      "market": "moneyline",
      "pick": "76ers ML",
      "odds": 270,
      "decimal_odds": 3.70,
      "model_prob": 0.38,
      "edge_pct": 11.0,
      "tier": "High",
      "bet_size": 25.00,
      "outcome": "win",
      "pnl": 67.50
    }
  ]
}
```

## Firestore Database Structure

Firestore is a NoSQL document database. Data is organized into collections and documents.

```
firestore/
├── daily_scans/                          # Collection — shared, one doc per day
│   └── {YYYY-MM-DD}/                     # Document ID = scan date
│       ├── scan_date: "2026-03-16"
│       ├── subtitle: "Monday, March 16, 2026 — NBA, NHL"
│       ├── games_analyzed: 10
│       ├── best_bet_title: "Suns +8.5 (-110) — 7.6% Edge"
│       ├── best_bet_desc: "Multiple models flag PHX spread value."
│       ├── created_at: Timestamp
│       └── picks/                        # Subcollection under each scan
│           └── {auto-id}/
│               ├── rank: 1
│               ├── sport: "NBA"
│               ├── event: "Suns @ Celtics"
│               ├── market: "Spread"
│               ├── pick: "Suns +8.5"
│               ├── odds: "-110"
│               ├── implied_pct: 52.4
│               ├── model_pct: 60.0
│               ├── edge_pct: 7.6
│               ├── tier: "High"
│               ├── notes: "Dimers gives PHX 53% to cover..."
│               ├── sources: "Dimers, BetMGM, Covers, OddsShark"
│               └── game_time: Timestamp
│
├── users/                                # Collection — one doc per user
│   └── {uid}/                            # Document ID = Firebase Auth UID
│       ├── email: "max@example.com"
│       ├── display_name: "Max"
│       ├── created_at: Timestamp
│       ├── bankroll/                     # Fields directly on user doc
│       │   ├── current: 550.23
│       │   ├── starting: 500.00
│       │   └── last_updated: Timestamp
│       └── bets/                         # Subcollection — per-user bet log
│           └── {auto-id}/
│               ├── pick_id: "reference to picks doc"
│               ├── date: "2026-03-16"
│               ├── sport: "NBA"
│               ├── event: "Suns @ Celtics"
│               ├── pick: "Suns +8.5"
│               ├── odds: "-110"
│               ├── decimal_odds: 1.909
│               ├── edge_pct: 7.6
│               ├── tier: "High"
│               ├── wager: 18.37
│               ├── outcome: "pending"
│               ├── pnl: null
│               └── created_at: Timestamp
```

## Firestore Security Rules

These rules enforce that users can only read/write their own data, while picks are readable by everyone.

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Daily scans and picks — readable by everyone, writable only by admin (Cloud Functions)
    match /daily_scans/{scanId} {
      allow read: if true;
      allow write: if false;  // Only Cloud Functions can write (uses admin SDK)

      match /picks/{pickId} {
        allow read: if true;
        allow write: if false;
      }
    }

    // Users — each user can only access their own document
    match /users/{userId} {
      allow read, write: if request.auth != null && request.auth.uid == userId;

      // Bets subcollection — same rule, only the owning user
      match /bets/{betId} {
        allow read, write: if request.auth != null && request.auth.uid == userId;
      }
    }
  }
}
```

## Core Business Logic

### Edge Calculation
```
implied_probability:
  negative odds: |odds| / (|odds| + 100)
  positive odds: 100 / (odds + 100)

edge = model_probability - implied_probability
```

### Kelly Criterion Bet Sizing
```
kelly_fraction = (edge * decimal_odds - 1) / (decimal_odds - 1)

Fractional Kelly by tier:
  High (ML/spread/total, 3% min edge):   kelly_fraction * 0.5
  Medium (props, 5% min edge):            kelly_fraction * 0.25
  Low (SGP/alt/niche, 8% min edge):       kelly_fraction * 0.125

bet_size = fractional_kelly * user's current_bankroll
```

### Safety Caps
- Max single bet: 5% of user's bankroll
- Max daily exposure: 15% of user's bankroll
- Drawdown warning: alert when bankroll drops 20% below starting

### Confidence Tiers
| Tier   | Markets                  | Min Edge |
|--------|--------------------------|----------|
| High   | ML, spread, total        | 3%       |
| Medium | Player props             | 5%       |
| Low    | SGP, alt lines, niche    | 8%       |

## Frontend Data Flow (using Firebase JS SDK)

No REST API needed. The React app talks directly to Firebase:

```javascript
// Auth
import { getAuth, signInWithPopup, GoogleAuthProvider, createUserWithEmailAndPassword } from 'firebase/auth';

// Read today's picks (shared — everyone sees the same thing)
import { getFirestore, collection, doc, getDoc, getDocs } from 'firebase/firestore';
const scanDoc = await getDoc(doc(db, 'daily_scans', '2026-03-16'));
const picks = await getDocs(collection(db, 'daily_scans', '2026-03-16', 'picks'));

// Read user's bankroll (private — only this user)
const userDoc = await getDoc(doc(db, 'users', auth.currentUser.uid));

// Read user's bets (private — only this user)
const bets = await getDocs(collection(db, 'users', auth.currentUser.uid, 'bets'));

// Log a bet
await addDoc(collection(db, 'users', auth.currentUser.uid, 'bets'), { ...betData });

// Update bankroll
await updateDoc(doc(db, 'users', auth.currentUser.uid), { 'bankroll.current': newAmount });
```

## Frontend Pages

### 1. Login / Signup
Simple email+password form with "Sign in with Google" button (one click via Firebase Auth popup). On signup, create a user document with $500 default bankroll (user can change).

### 2. Dashboard (main page, requires auth)
Keep the exact same visual design as the current `index.html` (dark theme, stat cards, picks table with expandable rows, bankroll cards, bet history table with P/L summary). The only differences:

- **Picks table** shows shared picks for everyone, but the "Bet Size" column is calculated from THIS user's bankroll
- **Bankroll cards** show THIS user's data
- **Bet history** shows THIS user's bets only
- **"Log Bet" button** on each pick row — clicking it creates a bet record for this user at the Kelly-recommended size (editable before confirming)
- **"Resolve" dropdown** on pending bets — mark win/loss/push, auto-updates bankroll

### 3. Settings
- Update starting bankroll
- Sync current bankroll (manual entry from DK account balance)
- Change display name
- Toggle email notifications for daily scan (stretch goal)

### 4. Public Picks View (no auth required)
A read-only version of just the picks table — no bankroll, no bet history, no Kelly sizing. This is the shareable link for people who don't want accounts.

## Tech Stack

- **Frontend:** React (Vite), Tailwind CSS, deployed on Netlify
- **Backend:** None needed — Firebase handles everything
- **Database:** Cloud Firestore (Firebase, free Spark plan)
- **Auth:** Firebase Auth (email/password + Google sign-in, free)
- **Daily scan:** Firebase Cloud Functions with a scheduled trigger (runs at 6 AM PT)

### Firebase Free Tier (Spark Plan) Limits
- Firestore: 1 GB storage, 50K reads/day, 20K writes/day — more than enough
- Auth: unlimited users, unlimited sign-ins
- Cloud Functions: 2M invocations/month on Blaze plan (pay-as-you-go, but a single daily cron costs ~$0/month)

Note: Cloud Functions require upgrading to the Blaze (pay-as-you-go) plan, but a single daily function invocation costs essentially nothing. If you want to stay on the free Spark plan, the daily scan can run as an external cron (e.g., from the existing Cowork scheduled task) that writes to Firestore using the Firebase Admin SDK.

## What to Build First (MVP Order)

1. **Firebase project** — create at console.firebase.google.com, enable Firestore + Auth
2. **React frontend** — port the current `index.html` to React components, add Firebase SDK
3. **Login/signup flow** — email + Google sign-in via Firebase Auth
4. **Dashboard** — fetch shared picks from `daily_scans` collection, fetch user bankroll + bets
5. **Log bet flow** — button on each pick → confirm wager amount → write to user's `bets` subcollection
6. **Resolve bet flow** — dropdown on pending bets → update outcome → recalculate bankroll
7. **Public picks page** — unauthenticated route showing just the picks table
8. **Firestore security rules** — deploy the rules above
9. **Daily scan automation** — Cloud Function or external cron that writes to `daily_scans` + `picks`
10. **Deploy** — frontend on Netlify, Firebase handles everything else

## Important Constraints

- **DraftKings Oregon only** — all odds and markets are specific to what's available on DK in Oregon
- **All in-season sports** — NFL, NBA, MLB, NHL, soccer, tennis, golf, MMA, whatever DK Oregon offers
- **No real-money automation** — this app NEVER places bets on DraftKings. Users log bets manually after placing them on DK themselves
- **Append-only bet history** — never delete or overwrite past bets
- **Responsible betting footer on every page:** "All models carry uncertainty. Edge estimates are probabilistic, not guarantees. Bet responsibly."
- **Game time filtering** — never show picks for games that have already started (check current time vs game_time)
- **Stale odds warning** — if odds data is >2 hours old for a same-day game, flag it

## Current UI to Preserve

The existing dashboard design (dark theme, purple/blue accents, stat cards, expandable pick rows, bet history with color-coded outcomes) is exactly what the multi-user version should look like. Port it to React components but keep the same CSS, layout, and visual feel. The CSS from the current `index.html` is included in the repo for reference.
