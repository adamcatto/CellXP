# Product screenshots

These images are generated with Playwright from deterministic local fixtures. Regenerate them with:

```bash
UPDATE_README_SCREENSHOTS=1 \
CELLXP_WEB_URL=http://127.0.0.1:3000 \
pnpm --dir src/frontend exec playwright test ../../tests/browser/readme-screenshots.spec.ts
```

Run the frontend in the mode noted by the screenshot test. Do not edit generated PNGs by hand.
