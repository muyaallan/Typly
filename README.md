# Typly

A two-part typing toolkit: a Python desktop app for local typing assistance and a hosted Next.js SaaS workspace for document management and validation.

---

## What's inside

| Component | Path | Stack | Purpose |
| --- | --- | --- | --- |
| **Typly Desktop** | `typly.py` | Python | Local typing companion compiled to `Typly.exe` |
| **Typly SaaS** | `typly-saas/` | Next.js 16, Prisma, NextAuth | Hosted typing workspace with document editing and validation |

---

## Typly Desktop

`typly.py` is a standalone Python application that provides typing assistance on the local machine. It is compiled to a single executable at `dist/Typly.exe` for distribution.

### Requirements

- Python 3.10+
- Dependencies listed in `requirements.txt`

### Run from source

```bash
pip install -r requirements.txt
python typly.py
```

### Build the executable

```bash
pip install pyinstaller
pyinstaller --onefile typly.py
```

The output binary appears at `dist/Typly.exe`. The `dist/` folder is gitignored and not committed.

---

## Typly SaaS

`typly-saas/` is a Next.js 16 application providing a hosted typing workspace. It includes:

- **Authentication** — NextAuth with a Prisma adapter
- **Documents** — Create, edit, and list typing documents
- **Validation** — JSON, YAML, and Markdown validation with inline errors
- **Agent polling** — Background polling endpoint for agent integrations
- **Deliverables** — Export and hand-off endpoint

### Requirements

- Node.js 18+
- SQLite (bundled via Prisma) for development, Postgres for production

### Setup

```bash
cd typly-saas
npm install
cp .env.example .env
npx prisma db push
npx prisma generate
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

See [`typly-saas/README.md`](typly-saas/README.md) for the full SaaS setup, API reference, and deployment notes.

---

## Project structure

```text
Typly/
├── typly.py                     # Python desktop app
├── requirements.txt             # Python dependencies
├── src/                         # Shared TypeScript utilities
│   ├── hooks/
│   │   ├── use-autosave.ts
│   │   └── use-debounce.ts
│   ├── lib/
│   │   ├── detect-type.ts
│   │   ├── document-types.ts
│   │   └── validation/
│   │       ├── index.ts
│   │       ├── json.ts
│   │       ├── markdown.ts
│   │       ├── types.ts
│   │       └── yaml.ts
│   ├── store/
│   │   └── editor-store.ts
│   └── types/
│       └── index.ts
│
├── typly-saas/                  # Next.js SaaS application
│   ├── prisma/
│   │   └── schema.prisma
│   ├── public/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── globals.css
│   │   │   └── api/
│   │   │       ├── auth/[...nextauth]/route.ts
│   │   │       ├── documents/route.ts
│   │   │       ├── documents/[id]/route.ts
│   │   │       ├── documents/[id]/validate/route.ts
│   │   │       ├── agent/poll/route.ts
│   │   │       └── deliver/route.ts
│   │   ├── components/
│   │   │   ├── app-shell/
│   │   │   ├── auth/
│   │   │   └── ui/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── store/
│   │   └── types/
│   ├── package.json
│   └── tsconfig.json
│
├── .gitignore
├── LICENSE
└── README.md
```

---

## Development

The two components are independent. Work on either without touching the other.

### Desktop app

```bash
python typly.py
```

### SaaS app

```bash
cd typly-saas
npm run dev
```

The `src/` directory at the root contains shared TypeScript utilities (`hooks/`, `lib/`, `store/`, `types/`) that provide document type detection and validation logic. These are not currently wired into the SaaS app's runtime but are kept as a shared reference.

---

## Environment variables

The SaaS app requires a `.env` file in `typly-saas/`. See `typly-saas/.env.example` for the template.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Prisma connection string |
| `NEXTAUTH_SECRET` | Session signing key (generate with `openssl rand -base64 32`) |
| `NEXTAUTH_URL` | Public URL of the app |

Never commit `.env`. It is gitignored at both the root and inside `typly-saas/`.

---

## Security notes

- `.env`, `dev.db`, `node_modules/`, `.next/`, and `dist/` are gitignored.
- The desktop executable and build artifacts are not committed.
- Session tokens are signed by NextAuth using `NEXTAUTH_SECRET`, which must be unique per environment.
- The Prisma schema is committed so new developers can set up the database with `npx prisma db push`.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Muya Allan.
```
