# Frontend Deployment

> Status: Draft v0.1. How the **TypeScript web client ships now** and how the **native macOS
> shell** ports onto the same wire contract later. UI contracts owned by `specs/interface/*`;
> wire owned by `api_contracts.md`. This spec is deployment-only — no scientific logic, no UI
> design decisions.

## 1. Current target: TypeScript web app

CellXP ships first as a **Next.js (App Router) web application** in TypeScript (strict),
co-located with the backend in `src/frontend/` (`architecture_overview.md` §3,
`ADR-0001`). The web app is the canonical client; everything in `specs/interface/*` is written
against it.

| Concern | Choice |
|---|---|
| Framework | Next.js App Router |
| Language | TypeScript strict |
| UI runtime | React (function components + hooks) |
| Styling | Tailwind + local `components/ui/*` primitives |
| Streaming | SSE via `fetch` / `EventSource`, `lib/streaming.ts` |
| API client | typed wrapper in `lib/api.ts`, generated from FastAPI OpenAPI 3.1 |
| 3D structure | Mol\* (default; lock-in pending) |
| Genome tracks | custom Canvas/SVG (`components/genome/*`) |
| Scientific plots | visx / D3 primitives |

## 2. Build & runtime modes

| Mode | When | How |
|---|---|---|
| Local dev | local iteration | `scripts/dev_frontend.sh` → `next dev` against `http://localhost:8000` API |
| Static export | doc/preview demos | `next export` — most CellXP features need server interactions, so this is preview-only and disables SSE-dependent surfaces |
| Self-hosted node | regime 1–2 | `next build && next start` → single Node process behind a reverse proxy |
| Containerized | regime 2–3 | `infra/docker/frontend.Dockerfile` (Node 20 alpine, multi-stage) + `infra/compose/` and `infra/k8s/` |
| Edge / CDN-fronted | regime 3 | static asset CDN in front of a Node origin, OR a Vercel-style deploy; SSR is fine but SSE termination MUST happen at the Node origin, not the CDN edge |

**SSE caveat.** Many CDNs and HTTP/2 intermediaries buffer event streams. The frontend
deployment MUST guarantee SSE passes through unbuffered (Cache-Control: no-transform, X-Accel-
Buffering: no, HTTP/1.1 keep-alive). Where the CDN forces buffering, route `/api/v1/runs/*/events`
to the origin directly (`api_contracts.md` §8).

## 3. Configuration

The frontend reads minimum runtime configuration from environment variables baked at build time
or surfaced via a server-rendered config endpoint:

```
NEXT_PUBLIC_API_BASE_URL=/api/v1            # same-origin or absolute URL
NEXT_PUBLIC_SSE_BASE_URL=/api/v1            # may differ when SSE routed elsewhere
NEXT_PUBLIC_DEPLOYMENT_NAME=cellxp-local
NEXT_PUBLIC_TELEMETRY_OPT_IN=false
```

Sensitive configuration (auth client secrets, etc.) is server-only and never reaches
`NEXT_PUBLIC_*`. The frontend never embeds an API key for the LLM or any other backend service
(`API-10`).

## 4. CORS, auth, and cross-origin use

- **Single-origin default.** The web app is served same-origin with the API in regimes 1–2 to
  avoid CORS entirely. The reverse proxy maps `/api/*` to the API process and everything else to
  Next.js.
- **Cross-origin deployments** (web app on CDN, API on a separate hostname) MUST configure CORS
  on the API allowlist explicitly (`api_contracts.md` §9). CORS is deny-by-default.
- **Auth.** Regime 1: loopback-bound session cookie. Regime 2–3: SSO with HttpOnly cookie or
  short-lived bearer in `Authorization` header. CSRF protections on mutating endpoints.

## 5. Generated client portability

The FastAPI OpenAPI document is the **single source of truth** for client types (`API-9`).
The web app's `lib/api.ts` is generated from it; CI fails if the generated client and the
served schema drift. Any future client (native macOS, CLI, third-party) MUST consume the same
OpenAPI document or JSON schema fixtures. No client may carry scientific logic that should live
server-side (`api_contracts.md` §10).

## 6. Future: native macOS app

The plan is to **port** the web client to a native macOS app once the web product is shipping
and the UX contracts have stabilized. The port targets the same REST/SSE wire and uses the
same artifact / event / selection schemas.

### 6.1 Recommended path

| Option | Trade-offs |
|---|---|
| **Tauri** (Rust shell + web-tech UI) | smallest delta from the web app; reuses React components and the OpenAPI client; native window/menu/notifications; reasonably small binary; good if we want to ship soon with one codebase |
| **SwiftUI + native renderers** | best macOS feel; opens the door to native Mol* alternatives (e.g. native Metal renderers); larger porting effort; requires duplicating renderers for genome/structure/origami |
| **Electron** | familiar but heavy; not recommended over Tauri for a science-app footprint |

**v1 plan: Tauri.** It minimizes the porting risk while delivering native window/menu/file
system integration. We revisit a full SwiftUI native build only if there are concrete UX wins
(e.g. extreme-performance structure rendering) that the web stack cannot meet.

### 6.2 Invariants the native shell MUST honor

- Consume the same REST/SSE contracts (`api_contracts.md`); no private backdoors.
- Implement the **pane registry**, **selection bus**, and **edit-action contract** identically
  (`interactive_panes.md` §4–§6); cross-platform panes must be functionally equivalent.
- Surface the same **review-gate / clarification cards** with the same approval semantics
  (`streaming_protocol.md` §7–§8).
- Emit telemetry on the same redacted schema (no biological payloads in logs).
- Default to **the user's local API** (loopback) and treat hosted-API connections as an
  explicit, audit-logged choice (`llm_service.md` §8, `chat_interface.md` §11).
- Honor the **macOS sandbox**: file/upload access via user-granted folder bookmarks; never silently
  access the home directory.

### 6.3 Local-only "single-app" mode

For the local-first user, the macOS shell SHOULD optionally bundle the backend (e.g. spawn a
local API process pointing at a bundled SQLite-compatible Postgres alternative, or a managed
local Postgres). This is a packaging exercise and does not change any contract — it makes the
desktop app a one-click install.

## 7. Performance & accessibility

- Strict **bundle-size budgets**: track first-contentful paint per surface; lazy-load heavy
  renderers (Mol\*, visx) per route/pane.
- **Code-splitting** by pane: only load the renderer when its pane mounts.
- **Service worker** for offline doc surfaces; SSE/chat surfaces are explicitly online-only.
- A11y: every interactive component meets the requirements in `interactive_panes.md` §9 and
  `chat_interface.md` §10.

## 8. Telemetry & privacy

- Frontend telemetry is **opt-in** and **redacted**: no message bodies, no entity names, no
  artifact payloads. Only feature usage, route timings, and error fingerprints.
- Errors reported back to the operator MUST NOT contain user content (`API-10`).
- Hosted-provider chips and consent gates render BEFORE the first private payload egress
  (`chat_interface.md` §11).

## 9. CI/CD

- Builds run on `.github/workflows/ci.yml`; container builds on
  `.github/workflows/docker.yml`; e2e against a real backend on
  `.github/workflows/evals.yml`.
- Type generation from OpenAPI runs in CI; build fails on drift (`API-9`).
- PRs that touch UI surfaces run visual-regression snapshots for pane chrome and chat layouts.
- Pre-release: smoke-test the web app against a regime-1 local stack end-to-end (load a
  genome, run a variant scoring, render the result in the genome browser).

## 10. Requirements

- **FED-1** The web client MUST consume only the published REST/SSE contracts; no private
  backdoors into Postgres / Redis / object store.
- **FED-2** SSE MUST pass through unbuffered between the client and the API process (no CDN
  buffering for run-event endpoints).
- **FED-3** The TypeScript API client MUST be generated from the FastAPI OpenAPI document;
  drift MUST fail CI (`API-9`).
- **FED-4** No API key for any service MUST be embedded in the client bundle.
- **FED-5** Same-origin deployment MUST be the default to avoid CORS; cross-origin MUST be
  deny-by-default and explicitly configured.
- **FED-6** The macOS native shell MUST consume the same wire contracts and MUST implement the
  pane registry, selection bus, and review/clarification semantics identically.
- **FED-7** Telemetry MUST be opt-in and MUST NOT contain biological content or message bodies.
- **FED-8** Hosted-provider use (LLM or other) MUST surface a consent gate in the UI before
  private payloads egress, on every client (web and native).

## 11. Open questions

- When to lock Mol\* (and visx) as deps vs. abstract behind a viewer-interface for a future
  native swap.
- Whether to ship a CLI client alongside web/macOS for scripted/batch use; if yes, this spec
  acquires a third sub-section.
- Single-app local bundle for macOS: SQLite-shim or bundled Postgres in the app bundle?

## 12. Related

`specs/interface/*` · `specs/interface/api_contracts.md` §10–§11 ·
`specs/serving/reasoning_llm_serving.md` · `specs/serving/agent_runtime_serving.md` ·
`documentation/explanation/architecture_overview.md` §3, §8 ·
`documentation/explanation/frontend_backend_boundary.md` · `infra/docker/frontend.Dockerfile` ·
`src/frontend/package.json`.
