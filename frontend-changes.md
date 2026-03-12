# Frontend Changes

## Code Quality Tooling

### What was added

#### Prettier (automatic code formatter)
Prettier is the frontend equivalent of Python's `black` — it enforces a single, opinionated code style across JS, CSS, and HTML with no manual decisions.

**New files:**
- `frontend/package.json` — declares Prettier as a dev dependency and exposes `npm run format` / `npm run format:check` / `npm run quality` scripts
- `frontend/.prettierrc` — formatting rules:
  - 100-character print width
  - 2-space indentation
  - Single quotes in JS
  - Semicolons required
  - Trailing commas where valid (ES5)
  - LF line endings
- `frontend/.prettierignore` — excludes `node_modules/`

#### Developer scripts
- `frontend/scripts/format.sh` — runs `prettier --write` to auto-format all `.js`, `.css`, and `.html` files
- `frontend/scripts/check-quality.sh` — runs `prettier --check` (read-only) and exits non-zero on violations; suitable for CI

### Formatting fixes applied to existing code

**`frontend/script.js`**
- Removed double blank line inside `setupEventListeners()` (between the `keypress` handler and the `// New Chat button` comment)
- Removed double blank line between `setupEventListeners()` and `sendMessage()`

### How to use

**Install dependencies** (one-time, requires Node.js):
```bash
cd frontend
npm install
```

**Auto-format all files:**
```bash
cd frontend
npm run format
# or directly:
./frontend/scripts/format.sh
```

**Check formatting without making changes** (e.g. in CI):
```bash
cd frontend
npm run format:check
# or directly:
./frontend/scripts/check-quality.sh
```
