/**
 * DK Edge Finder — Cloudflare Worker
 *
 * Serves the static site from the repo root and exposes a single API route
 * that dispatches the `place-bets.yml` workflow via GitHub's
 * `repository_dispatch` API. This is the ONLY persistent write path from the
 * site to server-side state — keeps `place_bets.py` as the single source of
 * truth for bet-record writes.
 *
 * Required secrets (set via `wrangler secret put <NAME>`):
 *   GITHUB_TOKEN — fine-grained PAT scoped to blueandyellow44/dk-edge-finder
 *                  with `Actions: Read and write` + `Metadata: Read-only`
 *
 * Bindings (in wrangler.jsonc):
 *   ASSETS — static asset binding for `.` (repo root)
 */

const REPO_OWNER = "blueandyellow44";
const REPO_NAME = "dk-edge-finder";
const DISPATCH_EVENT_TYPE = "place-bets";

// CORS is same-origin by default — only the deployed site can call this Worker
// unless you add explicit allowed origins. Keep this list tight.
const ALLOWED_ORIGINS = [
  "https://dk-edge-finder.blueandyellow44.workers.dev",
  // Add custom domain here if one is configured, e.g.:
  // "https://dk.example.com",
];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // API routes
    if (url.pathname === "/api/place-bets") {
      return handlePlaceBets(request, env);
    }
    if (url.pathname === "/api/health") {
      return jsonResponse({ ok: true, time: new Date().toISOString() });
    }

    // Everything else: static assets (index.html, data.json, etc.)
    return env.ASSETS.fetch(request);
  },
};

/**
 * POST /api/place-bets
 * Body: { picks: "all" | "0,1,2" | number[] }
 *
 * Dispatches a repository_dispatch event with the picks payload. The
 * `place-bets.yml` workflow receives it, runs `scripts/place_bets.py`, and
 * commits the updated `data.json` + `bankroll.json`.
 */
async function handlePlaceBets(request, env) {
  // Preflight / CORS
  if (request.method === "OPTIONS") {
    return corsResponse(request);
  }
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405, request);
  }

  // Origin check — cheap drive-by protection. The real auth is the PAT
  // being held server-side; origin check just keeps randos off the endpoint.
  const origin = request.headers.get("Origin") || "";
  const referer = request.headers.get("Referer") || "";
  const originOk =
    ALLOWED_ORIGINS.some((allowed) => origin === allowed || referer.startsWith(allowed)) ||
    // Also accept same-origin (Worker deployed domain serving the site)
    origin === new URL(request.url).origin;

  if (!originOk) {
    return jsonResponse(
      { error: "Forbidden origin", origin, referer },
      403,
      request
    );
  }

  if (!env.GITHUB_TOKEN) {
    return jsonResponse(
      { error: "Server misconfigured: GITHUB_TOKEN secret not set" },
      500,
      request
    );
  }

  // Parse body
  let body;
  try {
    body = await request.json();
  } catch (err) {
    return jsonResponse({ error: "Invalid JSON body" }, 400, request);
  }

  const picks = normalizePicks(body?.picks);
  if (!picks) {
    return jsonResponse(
      {
        error:
          'Body must include `picks` as "all", a comma-separated index string, or an array of indices.',
      },
      400,
      request
    );
  }

  // Dispatch the workflow via repository_dispatch
  const dispatchRes = await fetch(
    `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "dk-edge-finder-worker",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        event_type: DISPATCH_EVENT_TYPE,
        client_payload: {
          picks,
          triggered_at: new Date().toISOString(),
          source: "worker",
        },
      }),
    }
  );

  if (!dispatchRes.ok) {
    const text = await dispatchRes.text().catch(() => "");
    return jsonResponse(
      {
        error: "GitHub dispatch failed",
        status: dispatchRes.status,
        detail: text.slice(0, 500),
      },
      502,
      request
    );
  }

  // GitHub returns 204 No Content on success. There's no run_id to return —
  // the workflow queues and runs asynchronously. The client should poll
  // /data.json for the new bet to appear (or watch Actions tab).
  return jsonResponse(
    {
      ok: true,
      dispatched: picks,
      message:
        "Workflow dispatched. The bet will appear in data.json within ~1 minute.",
    },
    202,
    request
  );
}

/**
 * Accepts `"all"`, `"0,1,2"`, or `[0,1,2]` and returns a normalized string
 * that `scripts/place_bets.py` already understands (`"all"` or `"0,1,2"`).
 * Returns null if the input isn't one of those shapes.
 */
function normalizePicks(picks) {
  if (picks === "all") return "all";
  if (typeof picks === "string") {
    // Require comma-separated integers
    if (!/^\d+(,\d+)*$/.test(picks)) return null;
    return picks;
  }
  if (Array.isArray(picks)) {
    if (picks.length === 0) return null;
    if (!picks.every((n) => Number.isInteger(n) && n >= 0)) return null;
    return picks.join(",");
  }
  return null;
}

function jsonResponse(obj, status = 200, request = null) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  };
  if (request) {
    const origin = request.headers.get("Origin");
    if (origin) {
      headers["Access-Control-Allow-Origin"] = origin;
      headers["Access-Control-Allow-Credentials"] = "true";
      headers["Vary"] = "Origin";
    }
  }
  return new Response(JSON.stringify(obj, null, 2), { status, headers });
}

function corsResponse(request) {
  const origin = request.headers.get("Origin") || "*";
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
      Vary: "Origin",
    },
  });
}
