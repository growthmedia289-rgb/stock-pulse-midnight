# Deployment review — 28 October 2026

## Decision

**Local/private demonstration: verified for the tested paths. Public production: NOT signed off.**

All page templates render and the core preview interactions work. Passing a route or preview test does not establish that the Google project, optional deep-learning stack, Windows host or public hosting environment is ready.

## Results

| Check | Result | Scope |
|---|---|---|
| Automated application tests | 37 passed | Clean Linux Python 3.11.17 environment with the reviewed requirements |
| Browser layout tests | 40 passed | 10 routes at 390, 768, 1024 and 1440px; no whole-page horizontal overflow |
| Browser interactions | Passed | Registration/login/logout, watchlist add, holding dialog/save, analysis charts, screener filtering/sort/export, backtest rendering, safe chat text, mobile drawer |
| Dependency compatibility | Passed | Declared base requirements install together |
| Base dependency security audit | No known vulnerabilities reported | pip-audit of requirements.txt at the time of this review; not a guarantee of application security or an audit of optional ML packages |
| Public live price requests | Passed | INFY.NS and NIFTY 50 returned five daily bars |
| Live-data overview/analysis/portfolio/backtest | Passed | HTTP 200 and expected rendered chart/data sections in smoke tests |
| Random Forest on live histories | Passed | Explicit training on two NSE tickers, followed by analysis and a two-stock scan; not the full 45-stock load |
| Yahoo news scraping | Degraded | Fallback scraper timed out in smoke testing; pages continued without sentiment |
| Gemini replies | NOT verified | Requires a configured key, an available model and working project quota |
| LSTM training/inference | NOT verified end-to-end | Optional TensorFlow dependency and model artifacts not exercised here |
| FinBERT download/inference | NOT verified end-to-end | Optional PyTorch/Transformers/Hugging Face download not exercised here |
| Windows/DLL/GPU setup | NOT verified | Tests ran on Linux; this cannot establish your Windows runtime state |
| Public hosting/load/restarts | NOT verified | No deployment target was provided or modified |

## Problems found and corrected during this review

1. Cached daily prices could lose their source timezone and display the previous calendar date. Cache payloads now preserve the timezone; an automated regression check covers the round-trip.
2. Any registered account could submit model training requests. Training is now off by default, requires both ENABLE_WEB_TRAINING=1 and an existing account ID in ADMIN_USER_IDS, and returns 403 to other users. Both RF and LSTM training endpoints are checked.
3. Initial dependency pins included versions flagged by the package vulnerability database. Flask is now 3.1.3, Werkzeug 3.1.9, and scikit-learn 1.5.2. The application tests and browser checks were repeated after these changes. Retrain RF artifacts after updating; compatibility of pickles from other sklearn versions is not guaranteed.
4. Added an environment switch for Secure session cookies on HTTPS hosting. It is off for local HTTP and must be set to 1 on HTTPS deployment.

## Remaining public-release gates

- Select a hosting platform and use a production WSGI server. Do not expose the Flask development server in run.bat/app.py publicly. Flask's own deployment guidance: https://flask.palletsprojects.com/en/stable/deploying/
- Provide HTTPS, set SESSION_COOKIE_SECURE=1, and keep an environment-managed stable SECRET_KEY.
- Confirm persistent storage/backups for the database and models. An ephemeral host filesystem would lose accounts/holdings on redeploy. Review SQLite suitability for the intended concurrency.
- Keep web training disabled publicly. Move long scans/training to controlled jobs as load requires; the current thread lock is process-local.
- Add robust server-side authentication/API rate limiting. The browser-session cooldown can be bypassed by replacing cookies; it is not an abuse-control system.
- Verify actual Gemini replies using your configured project. Verify the optional LSTM and FinBERT pipeline if those features will be advertised as available.
- Install/audit the optional ML dependencies and test on the deployment OS, then smoke-test all enabled features in staging. The successful base-dependency audit does not cover optional torch/tensorflow/transformers packages.

Do not treat this package as production-approved merely because the interface loads.
