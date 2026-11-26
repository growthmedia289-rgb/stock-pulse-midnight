"""
FinBERT-based financial news sentiment analysis.
Loads model ONCE globally to avoid repeated 500MB downloads.
GPU-accelerated on GTX 1650 when available.
"""
import os
import torch
import threading
_model_lock = threading.RLock()

# ─── Global singleton ────────────────────────────────────────────────────────
_pipeline = None
_device   = -1   # -1 = CPU; 0 = GPU


def _get_device() -> int:
    """Prefer GPU (GTX 1650) to free CPU RAM."""
    if torch.cuda.is_available():
        total_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"[FinBERT] GPU detected ({total_mem:.1f} GB VRAM) — using GPU")
        return 0
    print("[FinBERT] No GPU — using CPU")
    return -1


def _load_pipeline():
    """Lazy-load FinBERT pipeline (called once per process)."""
    global _pipeline, _device
    if _pipeline is not None:
        return _pipeline

    from transformers import pipeline as hf_pipeline
    _device = _get_device()

    print("[FinBERT] Loading ProsusAI/finbert …")
    _pipeline = hf_pipeline(
        task="text-classification",
        model="ProsusAI/finbert",
        device=_device,
        truncation=True,
        max_length=512,
        padding=True,
    )
    print("[FinBERT] Model loaded ✓")
    return _pipeline


# ─── Public API ──────────────────────────────────────────────────────────────

LABEL_MAP = {'positive': 1.0, 'neutral': 0.0, 'negative': -1.0}


def _analyze_headlines(headlines: list) -> dict:
    """
    Analyze a list of news headlines.

    Returns:
        {
          'score':       float  [-1.0, 1.0]  overall sentiment
          'label':       str    'Positive' | 'Neutral' | 'Negative'
          'details':     list   per-headline results
          'confidence':  float  mean confidence
        }
    """
    if not headlines:
        return {'score': 0.0, 'label': 'Neutral', 'details': [], 'confidence': 0.0}

    pipe = _load_pipeline()

    # Process in small batches to respect 4 GB VRAM limit
    batch_size = 8
    all_results = []
    for i in range(0, len(headlines), batch_size):
        batch = headlines[i:i + batch_size]
        try:
            results = pipe(batch)
            all_results.extend(results)
        except Exception as e:
            print(f"[FinBERT] Batch error: {e}")
            raise RuntimeError("Sentiment inference is unavailable.") from e

    scores      = [LABEL_MAP.get(r['label'].lower(), 0.0) for r in all_results]
    confidences = [r['score'] for r in all_results]

    overall_score = sum(scores) / len(scores) if scores else 0.0
    avg_conf      = sum(confidences) / len(confidences) if confidences else 0.0

    if overall_score > 0.15:
        label = 'Positive'
    elif overall_score < -0.15:
        label = 'Negative'
    else:
        label = 'Neutral'

    details = [
        {
            'headline':   h,
            'sentiment':  r['label'].capitalize(),
            'confidence': round(r['score'] * 100, 1),
            'score':      LABEL_MAP.get(r['label'].lower(), 0.0),
        }
        for h, r in zip(headlines, all_results)
    ]

    return {
        'score':      round(overall_score, 4),
        'label':      label,
        'details':    details,
        'confidence': round(avg_conf * 100, 1),
    }


def sentiment_to_signal_boost(sentiment_score: float) -> float:
    """
    Convert sentiment score [-1, 1] to a probability boost [-0.10, +0.10].
    Used to adjust ML breakout probability.
    """
    return round(sentiment_score * 0.10, 4)


def analyze_headlines(headlines: list) -> dict:
    with _model_lock:
        return _analyze_headlines(headlines)
