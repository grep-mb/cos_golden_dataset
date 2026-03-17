# COS Dataset Explorer

A React + Vite app for browsing and searching the COS golden dataset. Displays product data from `data/golden_dataset.jsonl` with locally served product images.

## Prerequisites

- Node.js (v18+)
- Product data in `../data/golden_dataset.jsonl`
- Product images in `../data/images/` (optional, for local image display)

## Getting Started

```bash
# Install dependencies
npm install

# Start the development server
npm run dev
```

The app will be available at `http://localhost:5173`.

The `predev` script automatically converts the JSONL dataset to JSON before starting the dev server.

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start the dev server with HMR |
| `npm run build` | Build for production |
| `npm run preview` | Preview the production build |
| `npm run lint` | Run ESLint |

## How It Works

1. The `predev`/`prebuild` script (`scripts/convert-data.js`) reads `../data/golden_dataset.jsonl`, rewrites CDN image URLs to local `/images/` paths, and outputs `src/data/golden_dataset.json`.
2. A custom Vite plugin serves product images from `../data/images/` at the `/images/` route during development.
