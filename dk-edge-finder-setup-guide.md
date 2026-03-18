# DK Edge Finder — Setup Guide (Firebase)

Follow these steps in order. Each step tells you exactly where to go and what to click.

---

## Step 1: Create Your Firebase Project

Firebase is a free Google service that stores your users, bankrolls, and bets. You sign in with your Google account — no new account needed.

1. Go to [console.firebase.google.com](https://console.firebase.google.com)
2. Click **Create a project** (or "Add project")
3. Name it `dk-edge-finder` and click **Continue**
4. It asks about Google Analytics — you can turn it off (you don't need it). Click **Create project**
5. Wait about 30 seconds, then click **Continue**

You're now in your Firebase project dashboard.

---

## Step 2: Turn On the Database (Firestore)

1. In the left sidebar, click **Build** → **Firestore Database**
2. Click **Create database**
3. It asks about location — pick **nam5 (us-central)** or whichever is closest to you
4. Select **Start in test mode** (we'll lock it down later with security rules)
5. Click **Create**

Your database is now live.

---

## Step 3: Turn On Login (Authentication)

1. In the left sidebar, click **Build** → **Authentication**
2. Click **Get started**
3. Under "Sign-in providers", click **Email/Password**
4. Toggle the first switch to **Enabled**, click **Save**
5. Go back to the providers list, click **Google**
6. Toggle to **Enabled**, pick a support email (use yours), click **Save**

Users can now sign up with email or Google.

---

## Step 4: Get Your Firebase Config

Claude Code needs these values to connect the app to your Firebase project.

1. In the left sidebar, click the **gear icon** → **Project settings**
2. Scroll down to "Your apps" — click the **web icon** (`</>`)
3. Give it a nickname like `dk-edge-finder-web`, click **Register app**
4. You'll see a code block with your config. It looks like this:

```javascript
const firebaseConfig = {
  apiKey: "AIzaSy...",
  authDomain: "dk-edge-finder.firebaseapp.com",
  projectId: "dk-edge-finder",
  storageBucket: "dk-edge-finder.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abc123"
};
```

5. Copy this entire block and save it somewhere — Claude Code will need it

---

## Step 5: Set Up the Code

Claude Code will have built a project folder called `dk-edge-finder-app`. Open a terminal and navigate to it:

```
cd dk-edge-finder-app
```

Create your environment file:

```
cp .env.example .env
```

Open `.env` in any text editor and fill in the values from your Firebase config:

```
VITE_FIREBASE_API_KEY=AIzaSy...
VITE_FIREBASE_AUTH_DOMAIN=dk-edge-finder.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=dk-edge-finder
VITE_FIREBASE_STORAGE_BUCKET=dk-edge-finder.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
```

Save the file.

---

## Step 6: Test It Locally

In your terminal (still in the `dk-edge-finder-app` folder), run:

```
npm install
npm run dev
```

Open the URL it shows (usually `http://localhost:5173`). You should see the login page. Try creating an account and logging in.

Press `Ctrl+C` in the terminal when you're done testing.

---

## Step 7: Put It Online (Netlify)

1. Push the code to GitHub:
   - Create a new repo at [github.com/new](https://github.com/new) called `dk-edge-finder-app`
   - Push your code using GitHub Desktop (same as before)

2. Go to [netlify.com](https://netlify.com) and log in

3. Click **Add new site** → **Import an existing project** → **GitHub**

4. Select your `dk-edge-finder-app` repo

5. Fill in the deploy settings:
   - **Branch:** `main`
   - **Build command:** `npm run build`
   - **Publish directory:** `dist`

6. Click **Show advanced** → **New variable** and add each of these:
   - `VITE_FIREBASE_API_KEY` → your API key
   - `VITE_FIREBASE_AUTH_DOMAIN` → your auth domain
   - `VITE_FIREBASE_PROJECT_ID` → your project ID
   - `VITE_FIREBASE_STORAGE_BUCKET` → your storage bucket
   - `VITE_FIREBASE_MESSAGING_SENDER_ID` → your sender ID
   - `VITE_FIREBASE_APP_ID` → your app ID

7. Click **Deploy site**

8. Wait about a minute — Netlify gives you a URL like `something-random.netlify.app`. That's your live app. Share it with friends.

---

## Step 8: Lock Down Security Rules

Once the app is working, go back to Firebase and lock down the database:

1. Go to [console.firebase.google.com](https://console.firebase.google.com) → your project
2. Click **Firestore Database** → **Rules** tab
3. Replace the rules with what Claude Code provides (it enforces that each user can only see their own bankroll and bets, while picks are shared)
4. Click **Publish**

---

## Step 9: Daily Scan Automation

This puts fresh picks into the app every morning. Claude Code will set this up — it either runs as:

- A **Firebase Cloud Function** that triggers at 6 AM PT daily, or
- Your existing **Cowork scheduled task** that writes directly to Firestore

Either way, it scans DraftKings Oregon odds, calculates edges, and writes the day's picks to the shared database. Every user sees the same picks, but Kelly sizing adjusts to their own bankroll.

---

## How It All Fits Together

```
Your friends visit your Netlify URL
        ↓
They sign up with email or Google (one click)
        ↓
App loads today's shared picks from Firebase
        ↓
Kelly bet sizes are calculated using THEIR bankroll
        ↓
They click "Log Bet" when they place a bet on DK
        ↓
Their personal bankroll and bet history update
        ↓
Your data and their data never mix
```

---

## Troubleshooting

**"npm not found"** — You need Node.js. Download from [nodejs.org](https://nodejs.org) (pick LTS).

**App loads but shows no picks** — The daily scan hasn't run yet. Ask Claude Code to run an initial scan to seed Firebase with today's picks.

**Friends can't sign up** — Make sure Authentication is enabled (Step 3) and that the Firebase config values in Netlify match your project.

**Google sign-in not working** — In Firebase Console → Authentication → Settings → Authorized domains, add your Netlify URL (e.g., `something-random.netlify.app`).

**Picks not updating daily** — The scheduled scan function may not be deployed yet. Check with Claude Code.
