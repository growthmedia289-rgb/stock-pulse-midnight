# StockPulse · Midnight Research

A complete redesigned copy of your Flask project, with real backend routes and a clearly labelled illustrative preview mode. This is source code, not a deployed website.

## Start here on your Windows computer

1. Extract the ZIP to a NEW folder. Keep your current project as a backup.
2. Open PowerShell inside the extracted `StockPulse-Midnight` folder (the folder containing `app.py` and this README).
3. Your existing `stockpulse311` Conda environment can be reused. Install the updated web dependencies:

```powershell
conda run --no-capture-output -n stockpulse311 python -m pip install -r requirements.txt
```

If this environment does not exist on another computer, create it first:

```powershell
conda create -n stockpulse311 python=3.11 -y
```

4. Run the real-data application:

```powershell
conda run --no-capture-output -n stockpulse311 python app.py
```

5. Open http://127.0.0.1:5000 and create an account. If port 5000 is occupied, set `PORT=5001` in your local `.env` and open port 5001 instead.

`run.bat` is a shortcut using the same existing Conda environment. Activation scripts and changes to PowerShell execution policy are unnecessary.

## Explore the interface before live setup

Double-click `preview.bat` after dependencies are installed. Or in PowerShell:

```powershell
$env:STOCKPULSE_DEMO="1"
conda run --no-capture-output -n stockpulse311 python app.py
```

Register a test account, add a few holdings/watchlist stocks, and explore. Preview prices, company information, model outputs, headlines and AI replies are deterministic, illustrative data. Preview mode never calls Gemini or Yahoo Finance. Training is disabled. Example tickers: RELIANCE, TCS, INFY. The latest illustrative price date is 27 October 2026.

The login and holdings database is local and shared between modes. Test holdings are genuine database records; use a separate test account. To leave preview mode, stop the server with Ctrl+C and run:

```powershell
$env:STOCKPULSE_DEMO="0"
conda run --no-capture-output -n stockpulse311 python app.py
```

## Bring over your own data

Stop both servers first. This ZIP intentionally contains no API keys, user database, virtual environment, caches, or trained models.

- To preserve accounts and holdings, copy your old `instance/stockpulse.db` to this project's `instance/stockpulse.db` before starting the new app. Create the `instance` folder if needed. Back up the old file first. The five database tables retain their original names and fields.
- Do not reuse the old Random Forest model without retraining. This reviewed build updates scikit-learn from 1.3.2 to 1.5.2, and cross-version pickle compatibility is not guaranteed. Retrain models in a controlled local setup: this copy corrects training preprocessing and time-based evaluation. Models trained using the old mixed-ticker pipeline are not validated by this redesign.
- Copy your own `.env` locally or create it from `.env.example`. Do not upload or share the completed file.
- Start this extracted project; don't run the old project's `venv/Scripts/python.exe`.

## Optional machine learning dependencies

The site starts without PyTorch or TensorFlow. Prices, indicators, portfolio and indicator backtests do not need those frameworks. FinBERT sentiment and LSTM require their optional dependencies.

For the Windows setup discussed in your chat, install the official CPU PyTorch build:

```powershell
conda run --no-capture-output -n stockpulse311 python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
conda run --no-capture-output -n stockpulse311 python -m pip install -r requirements-models.txt
```

The CPU wheel avoids relying on CUDA. FinBERT may be slower on CPU. If PyTorch still reports a DLL error, check your Microsoft Visual C++ runtime installation. The ZIP cannot repair Windows system libraries. TensorFlow 2.17 on native Windows is CPU-only; CUDA GPU configuration is outside this package.

Web training is disabled by default and restricted to explicitly configured owner account IDs. This prevents newly registered users from replacing shared models.

For local training only: first create and sign in to your own account, then find its numeric ID in the local database. You can run this command from your project folder, replacing YOUR_USERNAME:

```powershell
conda run -n stockpulse311 python -c "from app import app, User; ctx=app.app_context(); ctx.push(); print(User.query.filter_by(username='YOUR_USERNAME').first().id)"
```

Set `ENABLE_WEB_TRAINING=1` and `ADMIN_USER_IDS=<that existing account ID>` in your local `.env`, restart the app, and train from **Model settings**. Set `ENABLE_WEB_TRAINING=0` again before public hosting. Unauthorised training requests return HTTP 403. Do not assign an ID before creating the intended owner account.

Train Random Forest and optionally LSTM in **Model settings** once locally authorised. Training runs explicitly and synchronously in this local app. A process lock prevents concurrent training jobs. Do not close the server while training. Prediction requests never start training automatically. FinBERT downloads its model on first use; internet access and disk space are required.

## Gemini configuration

Set `GEMINI_API_KEY` and `GEMINI_MODEL` in `.env`. Choose a model currently available in your Google AI Studio project; an old model name copied from another project may no longer be available. A missing key disables AI chat only. The assistant does not receive live prices, your holdings, or analysis context automatically. In-memory conversation history is capped and expires; it is not restored after restarting the app. API quota/billing remains controlled by your Google project.

## Interface details

- Midnight navy/teal palette, readable 15px body text, high contrast labels, visible focus styles and reduced-motion support.
- Responsive sidebar with keyboard focus handling; charts resize to their card containers. Tables scroll horizontally on small screens.
- Global ticker search and dashboard links open actual analysis. Exchange suffixes are normalised.
- Clear empty states, preserved analysis/screener/backtest inputs, exact loading messages, explicit disabled and error states.
- Price labels distinguish last available close from genuinely live prices. Fetch time is labelled separately from the price-bar date.
- Portfolio add dialog, unique purchase-lot deletion, grouped allocation, and explicit unavailable valuations when any price is missing.
- Sortable tables, ticker text filtering, and CSV exports of visible rows. CSV output guards spreadsheet formula prefixes.
- Chat prevents duplicate sends and uses text-only rendering to avoid HTML injection. It supports Enter/Shift+Enter, typing feedback, error messages, clear confirmation and retry-ready text.
- Login/register split layout, show/hide password, confirmation, server validation, CSRF tokens, and same-origin login redirects.
- Charts load bundled Plotly.js only on chart pages. Preview charts work without a CDN connection. There are no external fonts or icon dependencies. The Plotly license is included under static/vendor/.

## Calculation and model corrections

- Backtest closed-trade win rate; entry/exit fees included in realised trade P&L; final exits logged; same-bar re-entry prevented; complete equity/trade history returned. Comparisons use the selected stop-loss/take-profit settings.
- Missing price data never values a holding at zero. Cost basis and return percentages are shown separately.
- RSI handles zero-loss, zero-gain and flat windows. This project retains the original rolling-average RSI/ATR/ADX variants and simplified SuperTrend; values may differ from broker charts using Wilder smoothing or another SuperTrend definition.
- RF preprocessing and labels remain within each ticker. A shared calendar cutoff separates training/evaluation, with forward-target overlap excluded from training. Scalers fit training rows only.
- LSTM sequences stay within a ticker, align to the last input bar's target, and use separate validation windows. Scalers fit training data only.
- RF/LSTM score weights and sentiment adjustments are heuristic; they have not been optimised or calibrated here. Reported validation metrics are not investment-performance evidence. Existing saved models remain as reliable or unreliable as their original training.

## Verification

```powershell
conda run -n stockpulse311 python -m unittest discover -s tests -v
```

Tests use an isolated temporary SQLite database and illustrative prices. They cover authentication, CSRF, validation, stock search, all page routes, holding ownership, duplicate purchase lots, screener filters, API errors and backtest accounting. See `VALIDATION.md` for what was and was not tested in the delivered build.

## Practical limits

This is a local educational application, bound to 127.0.0.1 with debug disabled. Before public deployment it needs a production server, HTTPS, robust server-side rate limiting, persistent storage, stable environment-managed secrets and an external job queue for long operations. On HTTPS hosting, set `SESSION_COOKIE_SECURE=1`; leave it at 0 for local HTTP. Keep web training disabled publicly. See DEPLOYMENT-REVIEW.md for the current release decision. The session-level login cooldown is only a local convenience and can be reset by clearing cookies.

Market availability, finance news parsing, Gemini responses and local ML execution depend on third-party services and your machine. Alerts run on overview load and use a 0.5% proximity check, not crossing detection or background notifications. Backtests model daily-close fills, fractional shares and flat commissions, without slippage, taxes or intraday stop execution. No brokerage execution is implemented.

## Scroll animation update — 29 October 2026

Cards and section headings reveal once with a short upward fade as they enter view. Nearby cards stagger gently, with smaller movements on mobile. Forms, the chat panel, dialogs and sticky settings stay immediately usable. Reduced-motion preferences disable reveals, including changes made while the page is open. Keyboard/pointer interaction cancels motion on the target card. Content remains visible with JavaScript disabled or unsupported animation APIs. There is no scroll hijacking, parallax, number animation or external animation dependency.

## Premium video backgrounds — 29 October 2026

The three user-supplied finance clips are integrated as decorative backgrounds, with muted loop playback, dark navy overlays and a small scroll-linked depth shift. They are not market data.

- `market-lines`: landing, sign-in/register, analysis and screener.
- `capital-flow`: overview and portfolio.
- `coin-motion`: backtesting, AI assistant and model settings.

Only the assigned clip loads per page. Optimised MP4s are included with WebM alternatives and matching WebP posters. Pause/resume is remembered in this browser. System reduced-motion preferences use a still image and do not load a video on initial visit; Data Saver starts with a still image until the user chooses to play. Playback pauses while the tab is hidden. No video includes an audio track. Browser autoplay restrictions or video-load failures leave the poster visible. The native scroll position is never hijacked; these are ambient backgrounds plus section reveals, not frame-by-frame video scrubbing.

All media is served from `static/media/` in this package. Keep that folder when copying the site. No additional API key, video service or animation library is needed. Existing deployment-review limits still apply.
