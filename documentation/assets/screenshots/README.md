# Product screenshots

These images are generated with Playwright. Start the local API and CopilotKit frontend:

```bash
./scripts/dev_api.sh
NEXT_PUBLIC_CELLXP_CHAT_MODE=copilot ./scripts/dev_frontend.sh
```

Then regenerate the images:

```bash
UPDATE_README_SCREENSHOTS=1 \
CELLXP_WEB_URL=http://127.0.0.1:3000 \
pnpm --dir src/frontend exec playwright test readme-screenshots.spec.ts
```

The chat capture exercises the local deterministic runtime; the structure capture intercepts only
the artifact manifest with a deterministic PDB fixture. Do not edit generated PNGs by hand.
