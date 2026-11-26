import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from data.indicators import compute_all, ML_FEATURES
from config import Config

MODEL_PATH  = os.path.join(Config.MODEL_DIR, 'lstm_model.keras')
SCALER_PATH = os.path.join(Config.MODEL_DIR, 'lstm_scaler.pkl')

SEQ_LEN   = 30   # 30-day lookback window
BATCH_SIZE = 32   # Safe for GTX 1650 4GB VRAM
EPOCHS     = 30


def _configure_gpu():
    """Memory growth to avoid OOM on GTX 1650 4GB VRAM."""
    try:
        import tensorflow as tf
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            print(f"[LSTM] GPU enabled: {gpus[0].name}")
        else:
            print("[LSTM] No GPU found, using CPU.")
    except Exception as e:
        print(f"[LSTM] GPU config error: {e}")


def _build_model(seq_len: int, n_features: int):
    """LSTM architecture tuned for GTX 1650."""
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import (
        LSTM, Dense, Dropout, BatchNormalization, Bidirectional
    )
    from tensorflow.keras.regularizers import l2

    model = Sequential([
        Bidirectional(LSTM(64, return_sequences=True),
                      input_shape=(seq_len, n_features)),
        BatchNormalization(),
        Dropout(0.3),

        LSTM(32, return_sequences=False),
        BatchNormalization(),
        Dropout(0.2),

        Dense(16, activation='relu', kernel_regularizer=l2(1e-4)),
        Dense(1, activation='sigmoid')
    ])

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss='binary_crossentropy',
        metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
    )
    return model


def _create_sequences(X: np.ndarray, y: np.ndarray, seq_len: int):
    Xs, ys = [], []
    for i in range(len(X) - seq_len):
        Xs.append(X[i:i + seq_len])
        ys.append(y[i + seq_len])
    return np.array(Xs), np.array(ys)


def train(df: pd.DataFrame, future_days: int = 5, threshold: float = 0.03):
    """Train LSTM on OHLCV DataFrame."""
    _configure_gpu()
    import tensorflow as tf
    from tensorflow.keras.callbacks import (
        EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
    )
    import joblib

    from models.training_data import labelled_groups, cutoff_date
    groups = labelled_groups(df, future_days, threshold)
    cutoff = cutoff_date(groups)
    training_frames = [f[f['_target_end'] < cutoff] for _,f in groups]
    scaler = MinMaxScaler().fit(pd.concat(training_frames)[ML_FEATURES].values)
    train_x, train_y, val_x, val_y = [], [], [], []
    available = ML_FEATURES
    for _, frame in groups:
        transformed = scaler.transform(frame[ML_FEATURES].values)
        for end in range(SEQ_LEN - 1, len(frame)):
            window = transformed[end-SEQ_LEN+1:end+1]
            label = frame['Label'].iloc[end]
            if frame['_target_end'].iloc[end] < cutoff:
                train_x.append(window); train_y.append(label)
            elif frame.index[end-SEQ_LEN+1] >= cutoff:
                val_x.append(window); val_y.append(label)
    X_train, X_val = np.array(train_x), np.array(val_x)
    y_train, y_val = np.array(train_y), np.array(val_y)
    if len(X_train)<30 or len(X_val)<10 or len(set(y_train))<2 or len(set(y_val))<2:
        raise ValueError('More per-stock history and both target classes are needed for LSTM training.')

    print(f"[LSTM] Train: {X_train.shape}, Val: {X_val.shape}")

    model = _build_model(SEQ_LEN, len(available))

    callbacks = [
        EarlyStopping(patience=7, restore_best_weights=True, monitor='val_auc',
                      mode='max'),
        ReduceLROnPlateau(factor=0.5, patience=3, verbose=1),
        ModelCheckpoint(MODEL_PATH, save_best_only=True, monitor='val_auc',
                        mode='max'),
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        callbacks=callbacks,
        verbose=1,
        shuffle=False
    )

    os.makedirs(Config.MODEL_DIR, exist_ok=True)
    joblib.dump(scaler, SCALER_PATH)

    val_auc = max(history.history.get('val_auc', [0.0]))
    print(f"[LSTM] Best Val AUC: {val_auc:.3f}")

    return model, scaler, {'val_auc': val_auc, 'features': available}


def load_model():
    import tensorflow as tf
    import joblib
    if not os.path.exists(MODEL_PATH):
        return None, None
    model  = tf.keras.models.load_model(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    return model, scaler


def predict_breakout(df: pd.DataFrame) -> dict:
    """Predict breakout probability using LSTM."""
    _configure_gpu()
    model, scaler = load_model()

    if model is None:
        print("[LSTM] No model saved. Training now…")
        raise ValueError("LSTM is not trained. Open Model settings.")

    df_ind    = compute_all(df)
    available = [f for f in ML_FEATURES if f in df_ind.columns]
    df_ind = df_ind.replace([np.inf, -np.inf], np.nan)
    if df_ind[ML_FEATURES].tail(SEQ_LEN).isna().any().any():
        return {"breakout_probability": None, "signal": "INSUFFICIENT DATA"}
    df_ind.dropna(subset=ML_FEATURES, inplace=True)

    if len(df_ind) < SEQ_LEN:
        return {'breakout_probability': 50.0, 'signal': 'INSUFFICIENT DATA'}

    X_raw    = df_ind[available].values
    X_scaled = scaler.transform(X_raw)
    seq      = X_scaled[-SEQ_LEN:][np.newaxis, ...]  # (1, 30, n_features)

    prob   = float(model.predict(seq, verbose=0)[0][0])
    signal = ('STRONG BUY' if prob > 0.70 else
              'BUY'        if prob > 0.55 else
              'NEUTRAL'    if prob > 0.40 else
              'SELL')

    return {
        'breakout_probability': round(prob * 100, 2),
        'signal': signal,
    }
