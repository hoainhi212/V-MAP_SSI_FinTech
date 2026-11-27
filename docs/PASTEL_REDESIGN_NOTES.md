# V-MAP Pastel redesign

## Changes
- Replaced the old tab-based layout with one sidebar radio navigation for the five main screens.
- Updated shared UI styles to a bright pastel palette (lavender, blush, mint, baby blue), rounded cards, and Nunito typography with system fallback.
- Redesigned PDF palette, title hierarchy, metadata panel, table striping, and footer accent.
- Kept existing screen render functions, SSI/data-access interfaces, and financial indicator calculations unchanged.

## Important limitation
The provided archive does not contain `src/vmap/data/`. The dashboard imports `vmap.data.db.Database`, so end-to-end runtime verification is not possible until that package is restored. Python syntax compilation passed.
