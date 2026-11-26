# Delivery verification

## Passed

- 37 automated functional checks: public/authenticated routes, account validation, CSRF handling, dashboard ticker search, analysis GET/POST, duplicate purchase lots, holding ownership on deletion, missing-price rendering, watchlist normalisation, screener filtering, chat API validation/rate cooldown, backtest accounting, calendar split boundaries, RF train/save/load/inference, and RSI boundary cases.
- Real Chromium browser interactions: account registration/sign-in, adding a watchlist entry, holding dialog/save, analysis charts, screener sorting and text filtering, CSV download, backtest result rendering, safe text-only chat output and mobile menu Escape/focus behaviour.
- 40 route/viewport layout checks across 390px, 768px, 1024px and 1440px. No whole-page horizontal overflow. Wide tables remain scrollable inside their cards. No browser JavaScript exceptions during these checks.
- Visual inspection of desktop overview/analysis and mobile overview/register/holding-dialog screenshots; spacing, chart grids, sidebar label and dialog close control adjusted after inspection.
- Template form audit: explicit/associated labels, unique IDs and CSRF tokens.
- Python compilation, JavaScript syntax and CSS parsing.
- Preview route checks use deterministic illustrative prices and an isolated test database. Chart checks use the bundled Plotly.js library.

## Not established by these checks

- Ongoing availability or quality of Yahoo Finance / Gemini services, current quotas, or model access in your Google project. Public price requests and core live-price page flows were smoke-tested; Gemini replies were not.
- Windows-specific installation, system DLLs or GPU operation. The reviewed build was verified on Linux with Python 3.11.17 and the declared base dependencies; Windows commands are provided for your existing Conda setup.
- End-to-end TensorFlow LSTM training or a first-time FinBERT model download/inference in this environment. These remain optional dependencies and are loaded only when needed. RF training/inference was tested on illustrative data and two live NSE histories, not evaluated for investment performance.
- Statistical profitability, calibrated financial probabilities, or public-production security. No such claims are made.

## Contents intentionally omitted

Actual API credentials, user databases, session secrets, caches, existing trained models, virtual environments and compiled Python bytecode. Copy your own local data only as described in README.md.

See DEPLOYMENT-REVIEW.md for the expanded review, corrected problems, and outstanding public-release gates.

## Video / scroll update verification — 29 October 2026

The 37 existing application tests passed again on the Linux Python 3.12 test runtime with the declared base requirements installed. In Chromium, 21 authenticated route/viewport combinations were checked at 390, 768 and 1440 pixels, with no JavaScript exceptions or whole-page horizontal overflow. Background selection, muted playback, pause/resume persistence, reduced-motion changes, no-video network requests on initial reduced-motion visits, no-JavaScript poster fallback, and portfolio dialog interaction were checked. MP4 files were inspected to confirm 720p video with no audio stream; this Chromium build used the WebM compatibility path because it lacks an H.264 decoder. MP4 playback on Safari/Windows was not directly tested.
