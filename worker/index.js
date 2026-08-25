import { readFile } from "node:fs/promises";
import { renderSpec } from "./render.js";

/**
 * THRAANSH external FFmpeg render worker.
 *
 * Runs anywhere Node 20 + FFmpeg are available (container, VPS, laptop).
 * It only talks outbound HTTP to the THRAANSH app — no database credentials,
 * no service-role key, no inbound ports.
 *
 *   lease  -> POST {BASE}/api/public/render/next
 *   beat   -> POST {BASE}/api/public/render/heartbeat
 *   report -> POST {BASE}/api/public/render/{jobId}/progress
 *   finish -> POST {BASE}/api/public/render/{jobId}/complete
 *
 * MP4 and thumbnail are uploaded with the signed upload URLs returned by the
 * lease, straight into the private thraansh-videos / thraansh-thumbnails
 * buckets. A failed render reports the real error; it never fabricates output.
 */

let BASE = (process.env.THRAANSH_BASE_URL || "").replace(/\/$/, "");
const STATIC_SECRET = process.env.RENDER_WORKER_SECRET || "";
const WORKER_ID = process.env.WORKER_ID || `worker-${Math.random().toString(36).slice(2, 8)}`;
const POLL_MS = Number(process.env.POLL_INTERVAL_MS || 15000);
const RUN_ONCE = process.env.RUN_ONCE === "1";
/** Drain mode: exit after N consecutive empty polls (0 = never exit). */
const IDLE_EXITS = Number(process.env.IDLE_EXITS || 0);
/** Hard stop so a scheduled runner can never hang (minutes, 0 = unlimited). */
const MAX_RUNTIME_MIN = Number(process.env.MAX_RUNTIME_MIN || 0);
const VERSION = "1.1.0";

/**
 * Auth: a static RENDER_WORKER_SECRET when present (self-hosted runners), or
 * the GitHub Actions OIDC identity token (no repository secret needed — the
 * app verifies the token against GitHub's JWKS and pins it to our repo).
 */
const OIDC_REQUEST_URL = process.env.ACTIONS_ID_TOKEN_REQUEST_URL || "";
const OIDC_REQUEST_TOKEN = process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN || "";
const OIDC_AUDIENCE = "thraansh-render-worker";
let oidcCache = { token: "", expiresAt: 0 };

async function getAuthToken() {
  if (STATIC_SECRET) return STATIC_SECRET;
  if (!OIDC_REQUEST_URL || !OIDC_REQUEST_TOKEN) return "";
  const now = Date.now();
  if (oidcCache.token && oidcCache.expiresAt > now + 60_000) return oidcCache.token;
  const res = await fetch(`${OIDC_REQUEST_URL}&audience=${OIDC_AUDIENCE}`, {
    headers: { authorization: `Bearer ${OIDC_REQUEST_TOKEN}` },
  });
  if (!res.ok) throw new Error(`OIDC token request failed (${res.status})`);
  const json = await res.json();
  // OIDC tokens live ~10 minutes; refresh conservatively after 4.
  oidcCache = { token: json.value, expiresAt: now + 4 * 60_000 };
  return oidcCache.token;
}

if (!BASE) {
  console.error("THRAANSH_BASE_URL is required. See worker/README.md.");
  process.exit(1);
}
if (!STATIC_SECRET && !OIDC_REQUEST_URL) {
  // Scheduled runs without credentials have nothing to do — exit quietly
  // instead of failing the workflow red.
  console.log("no RENDER_WORKER_SECRET and no OIDC environment — nothing to do, exiting");
  process.exit(0);
}

const log = (...a) => console.log(new Date().toISOString(), `[${WORKER_ID}]`, ...a);

/**
 * Some THRAANSH hostnames redirect (apex -> www). A cross-origin redirect makes
 * fetch drop the Authorization header, which surfaces as a confusing 401, so the
 * canonical origin is resolved once at startup and used for every call.
 */
async function resolveBase() {
  try {
    const res = await fetch(`${BASE}/robots.txt`, { redirect: "follow" });
    const finalOrigin = new URL(res.url).origin;
    if (finalOrigin && finalOrigin !== new URL(BASE).origin) {
      log("base URL redirects — using", finalOrigin);
      BASE = finalOrigin;
    }
  } catch {
    /* keep configured base */
  }
}

async function api(pathname, body) {
  const token = await getAuthToken();
  const res = await fetch(`${BASE}${pathname}`, {
    method: "POST",
    redirect: "manual",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (res.status >= 300 && res.status < 400 && res.headers.get("location")) {
    const target = new URL(res.headers.get("location"), `${BASE}${pathname}`);
    BASE = target.origin;
    const retry = await fetch(target, {
      method: "POST",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: JSON.stringify(body ?? {}),
    });
    const t = await retry.text();
    if (!retry.ok) throw new Error(`${pathname} failed (${retry.status}): ${t.slice(0, 300)}`);
    return t ? JSON.parse(t) : null;
  }
  const text = await res.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON error body */
  }
  if (!res.ok) throw new Error(`${pathname} failed (${res.status}): ${text.slice(0, 300)}`);
  return json;
}

async function heartbeat(status, jobId, note) {
  try {
    await api("/api/public/render/heartbeat", {
      worker_id: WORKER_ID,
      version: VERSION,
      status,
      job_id: jobId ?? null,
      note: note ?? null,
    });
  } catch (e) {
    log("heartbeat failed:", e.message);
  }
}

async function uploadSigned(upload, filePath, contentType) {
  if (!upload?.signedUrl && !upload?.signed_url) {
    throw new Error("The app did not return a signed upload URL for this job");
  }
  const url = upload.signedUrl || upload.signed_url;
  const absolute = url.startsWith("http") ? url : `${new URL(BASE).origin}${url}`;
  const body = await readFile(filePath);
  const res = await fetch(absolute, {
    method: "PUT",
    headers: { "content-type": contentType, "x-upsert": "true" },
    body,
  });
  if (!res.ok) throw new Error(`Storage upload failed (${res.status}): ${(await res.text()).slice(0, 200)}`);
  return upload.path;
}

async function processJob(job) {
  log("leased job", job.id, "video", job.video_id);
  await heartbeat("RENDERING", job.id, "rendering");

  let lastReported = -1;
  const onProgress = (p) => {
    if (p - lastReported < 5) return;
    lastReported = p;
    api(`/api/public/render/${job.id}/progress`, { lease_token: job.lease_token, progress: p }).catch((e) =>
      log("progress report failed:", e.message),
    );
  };

  let output = null;
  try {
    output = await renderSpec(job.spec, { onProgress });
    const videoPath = await uploadSigned(job.upload?.video, output.videoFile, "video/mp4");
    const thumbPath = await uploadSigned(job.upload?.thumbnail, output.thumbFile, "image/jpeg");

    await api(`/api/public/render/${job.id}/complete`, {
      lease_token: job.lease_token,
      ok: true,
      video_path: videoPath,
      thumbnail_path: thumbPath,
      duration_sec: Math.round(output.durationSec),
      size_bytes: output.sizeBytes,
    });
    log("job", job.id, "completed:", Math.round(output.durationSec), "s,", output.sizeBytes, "bytes");
    await heartbeat("IDLE", null, "last job completed");
  } catch (err) {
    const message = String(err?.message || err).slice(0, 1500);
    log("job", job.id, "FAILED:", message);
    try {
      await api(`/api/public/render/${job.id}/complete`, {
        lease_token: job.lease_token,
        ok: false,
        error: message,
      });
    } catch (e) {
      log("could not report failure:", e.message);
    }
    await heartbeat("IDLE", null, `last job failed: ${message.slice(0, 200)}`);
  } finally {
    if (output?.cleanup) await output.cleanup().catch(() => {});
  }
}

async function tick() {
  const res = await api("/api/public/render/next", { worker_id: WORKER_ID });
  if (!res?.job) {
    await heartbeat("IDLE", null, "no queued jobs");
    return false;
  }
  await processJob(res.job);
  return true;
}

async function main() {
  await resolveBase();
  log("starting against", BASE, "poll every", POLL_MS, "ms");
  await heartbeat("IDLE", null, "worker started");
  const deadline = MAX_RUNTIME_MIN ? Date.now() + MAX_RUNTIME_MIN * 60_000 : 0;
  let idle = 0;
  for (;;) {
    if (deadline && Date.now() > deadline) {
      log("max runtime reached — exiting cleanly");
      await heartbeat("STOPPED", null, "max runtime reached");
      return;
    }
    try {
      const worked = await tick();
      if (RUN_ONCE) return;
      if (worked) {
        idle = 0;
        continue;
      }
      idle += 1;
      if (IDLE_EXITS && idle >= IDLE_EXITS) {
        log("queue empty — exiting drain run");
        await heartbeat("STOPPED", null, "drain run finished, queue empty");
        return;
      }
      await new Promise((r) => setTimeout(r, POLL_MS));
    } catch (e) {
      log("poll error:", e.message);
      await heartbeat("ERROR", null, e.message.slice(0, 300));
      if (RUN_ONCE) process.exitCode = 1;
      if (RUN_ONCE) return;
      await new Promise((r) => setTimeout(r, POLL_MS));
    }
  }
}

for (const sig of ["SIGINT", "SIGTERM"]) {
  process.on(sig, async () => {
    await heartbeat("STOPPED", null, `received ${sig}`);
    process.exit(0);
  });
}

main().catch((e) => {
  console.error("fatal:", e);
  process.exit(1);
});
