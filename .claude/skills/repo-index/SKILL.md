---
name: repo-index
description: Build, maintain, and query a comprehensive repo index (.ai/index/) that maps every file to its purpose, key symbols, dependencies, and related files. Use at the start of EVERY session to get a fast map of the codebase, whenever planning changes that span multiple files, and after significant refactors to update the index. Triggers: "show me the index", "update index", starting work in unfamiliar area, planning cross-file changes, need to understand file relationships.
---

# Repo Index (LLM Wiki)

This repo maintains a machine-readable codebase index in `.ai/index/` to eliminate guesswork about session context and planning. The index acts as a "table of contents" for the entire codebase - every tracked file is referenced with its purpose, key exports/symbols, and relationships to other files.

The index is committed to git (like `.ai/sessions/` and `.ai/decisions/`) so it stays in sync with the codebase and helps future sessions understand the structure immediately.

## Goals

- **Complete coverage**: Index all source files (exclude node_modules, dist, build, __pycache__, coverage, etc.)
- **Fast orientation**: Answer "what does this file do?" and "where is X implemented?" without reading every file
- **Relationship mapping**: Track imports/exports, dependencies, and "related files" to make cross-file planning trivial
- **Session context**: Provide a compact view of relevant parts of the codebase for the current task
- **Keep in sync**: Update incrementally when files change

## Directory structure

```
.ai/index/
├── README.md           # Index format and maintenance rules
├── files/              # Per-file index entries (one .md per source file, or grouped by dir)
│   ├── <path-md>/      # Mirrored directory structure as .md filenames with path separators encoded
│   │   └── file.ts.md
│   └── ...
├── toc.md              # Master table of contents - all files with one-line descriptions
├── symbols.md          # Cross-reference: symbol name → files that define/export it
├── modules.md          # High-level module map (by top-level dirs)
└── graph.json          # Machine-readable dependency graph (imports/exports/deps)
```

## When to use this skill

**At session start (recommended, lightweight):**
1. Read `toc.md` and `modules.md` to get a bird's eye view
2. If task is focused, read only files entries relevant to the topic
3. If unfamiliar with repo, skim symbols.md to find key classes/functions

**During planning (important for cross-file work):**
1. Read file entries for files you plan to modify
2. Check `graph.json` or related files in entries to understand blast radius
3. Update plan with concrete file paths from the index

**After changes (maintenance):**
1. For any file created/modified/deleted, update its index entry
2. Rebuild affected parts of toc.md, symbols.md, graph.json
3. Keep index consistent with actual code

## Index file entry format

Each source file gets an index entry at `.ai/index/files/<encoded-path>.md`. Encode path separators as `__` or use a stable mapping.

Example: `src/auth/actions/login.action.ts` → `.ai/index/files/src__auth__actions__login.action.ts.md`

```markdown
# src/auth/actions/login.action.ts

- **Type**: Action (or Component/Service/Util/Config/Type/Hook/Route/Test/Other)
- **Purpose**: Short one-line description of what this file does
- **Last indexed**: YYYY-MM-DD HH:mm

## Key symbols
- `login()` - main action handler
- `LoginSchema` - zod validation schema
- `LoginRequest` - request type

## Imports
- `@contract/auth` - shared contract types
- `../helpers/auth.helper` - AuthHelper

## Exports
- `login` (default export or named)

## Dependencies
- External: zod, bcrypt, jsonwebtoken (if notable)
- Internal: modules/auth/helpers, contract/auth

## Related files
- src/auth/helpers/auth.helper.ts - shared auth logic
- src/auth/routes/auth.routes.ts - wires this action
- contract/auth/auth.contract.ts - API contract

## Notes
Any non-obvious behavior, gotchas, or important context for agents.

## TODO (index)
If index is stale relative to file, note what needs updating.
```

## Master TOC format (`toc.md`)

Keep sorted by path. One line per file.

```markdown
# Repo Index TOC

Generated: YYYY-MM-DD HH:mm

## Core (example grouping by top-level)
- [src/auth/actions/login.action.ts](files/src__auth__actions__login.action.ts.md) - Handles user login flow
- [src/auth/helpers/auth.helper.ts](files/src__auth__actions__... no, better link to actual encoded path) - Auth utilities

... all files ...
```

## Symbols index format (`symbols.md`)

Group by symbol name for quick lookup.

```markdown
# Symbols Index

| Symbol | Kind | Defined in | Exports |
|---|---|---|---|
| login | function/action | src/auth/actions/login.action.ts | default/named |
| AuthHelper | namespace/object | src/auth/helpers/auth.helper.ts | named export object |
```

## Graph JSON (`graph.json`)

Machine-readable for understanding relationships.

```json
{
  "generated": "2026-10-07T12:34:00Z",
  "files": {
    "src/auth/actions/login.action.ts": {
      "path": "src/auth/actions/login.action.ts",
      "type": "action",
      "imports": ["src/auth/helpers/auth.helper.ts", "@contract/auth"],
      "exports": ["login"],
      "depsInternal": ["src/auth/helpers/auth.helper.ts"],
      "depsExternal": ["zod"]
    }
  }
}
```

## Building the index (first time)

1. **Discover files**: Glob all source files, skip vendor dirs (node_modules, dist, build, out, .next, coverage, __pycache__, .git, .ai/index)
2. **Categorize**: Infer type by path/name (actions, components, services, utils, routes, hooks, types, schemas, tests, etc.)
3. **Extract symbols**: Read each file to get exports (export default, named exports, class/function declarations)
4. **Extract imports**: Get internal imports (relative ./../ or src/ aliases) and external deps
5. **Generate entries**: Write per-file entries
6. **Build aggregates**: toc.md, symbols.md, graph.json
7. **Write README.md** explaining the index

Use efficient tools: glob to find files, read files in batches. Keep it fast.

## Maintaining the index

**Incremental updates** (preferred):
- When a file is created: add entry, update aggregates
- When a file is modified: refresh its entry (symbols/imports may change)
- When a file is deleted: remove entry, update aggregates
- When many files change (refactor): can rebuild affected modules

**Full rebuild** (if index seems inconsistent):
- Delete `.ai/index/files/` and rebuild from scratch
- This is safe and ensures completeness

**Staleness guard**: Each entry has `Last indexed` timestamp. If source file mtime > index mtime, treat as potentially stale.

## Reading strategy for sessions

1. **Start lean**: Read toc.md (or modules.md) only
2. **Find relevant**: Grep for topic terms in toc.md, symbols.md, or graph.json
3. **Drill down**: Read specific file entries that match the task
4. **Load code on-demand**: Only read actual source files when you need to edit them
5. **Avoid loading all entries**: There could be hundreds of files

## Integration with repo-memory

- repo-index complements repo-memory: memory stores *history* (what happened, why decisions made), index stores *structure* (how code is organized, file relationships)
- At session start: can load both - memory for recent work/decisions, index for codebase map
- When planning: use index to understand blast radius; record decisions in repo-memory
- After large refactors: update index

## PII & secrets

Index files describe code structure only - they never contain secrets, credentials, or PII. Just paths, symbol names, import statements. No actual values.

## Example quick queries

- "Where is user auth implemented?" → look up "login", "authenticate", "AuthHelper" in symbols.md
- "What files import from auth helper?" → check graph.json or grep in index
- "Show me all API route files" → filter toc.md by "routes"
- "Planning to change User type - what depends on it?" → find type in symbols.md, trace usages via graph.json

---

# Implementation notes

- Encode file paths in filenames: replace `/` with `__`, keep extensions. Example: `src/foo/bar.ts` → `src__foo__bar.ts.md`
- Skip these dirs when indexing: `node_modules`, `dist`, `build`, `out`, `.next`, `coverage`, `__pycache__`, `.git`, `.ai/index`, `vendor`, `target`, `bin`, `obj`
- Common source extensions: `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs`, `.py`, `.go`, `.rs`, `.java`, `.kt`, `.rb`, `.php`, `.swift`, `.cs`, `.cpp`, `.c`, `.h`, `.hpp`, `.scala`, `.clj`, `.hs`, `.ex`, `.exs`, `.vue`, `.svelte`
- For each file, extract: ES exports (`export default`, `export const`, `export function`, `export class`, `export type`, `export interface`), CommonJS (`module.exports`), and imports (`import ... from`, `require()`)
- Keep descriptions terse (1 line). Focus on "what" not "how"
- Update index as part of completing tasks that change code structure
- Index is best effort but should be comprehensive for the main codebase

## In this repo

The index is **not built yet**. The `.ai/index/` directory does not exist; the session and decisions folders are present, the index is not. Building it is a separate, opt-in step — ~70 source files across `core/bot/`, `core/ml/`, `core/node-api/src/`, `core/pca-backend/src/`, plus the root compose/env files. Do not generate the index silently; tell the user the estimated scope and get approval first.
