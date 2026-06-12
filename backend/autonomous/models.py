"""
Model suite for the autonomous NEPSE prediction platform.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, mean_absolute_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from ..settings import Settings, get_settings
from .features import HORIZONS, feature_columns

logger = logging.getLogger("nepse-alpha.autonomous.models")

try:
    from xgboost import XGBClassifier, XGBRegressor

    HAS_XGBOOST = True
except Exception:
    HAS_XGBOOST = False
    XGBClassifier = None
    XGBRegressor = None

try:
    from lightgbm import LGBMClassifier, LGBMRegressor

    HAS_LIGHTGBM = True
except Exception:
    HAS_LIGHTGBM = False
    LGBMClassifier = None
    LGBMRegressor = None

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    HAS_TORCH = True
except Exception:
    HAS_TORCH = False
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None

try:
    import gymnasium as gym
    from stable_baselines3 import PPO

    HAS_PPO = True
except Exception:
    HAS_PPO = False
    gym = None
    PPO = None


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _torch_xla_device() -> Any:
    try:
        import torch_xla.core.xla_model as xm

        return xm.xla_device()
    except Exception as exc:
        logger.warning("TPU requested but torch_xla is unavailable (%s); falling back to CPU.", exc)
        return None


def _torch_device() -> Any:
    if not HAS_TORCH:
        return None
    if os.getenv("NEPSE_FORCE_CPU", "").strip().lower() in {"1", "true", "yes"}:
        return torch.device("cpu")
    requested = os.getenv("NEPSE_DEVICE", "").strip().lower()
    if requested in {"tpu", "xla"}:
        device = _torch_xla_device()
        return device if device is not None else torch.device("cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA requested but no GPU is available; falling back to CPU.")
        return torch.device("cpu")
    if requested:
        return torch.device(requested)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _sync_xla(device: Any) -> None:
    if device is not None and getattr(device, "type", "") == "xla":
        import torch_xla.core.xla_model as xm

        xm.mark_step()


def _build_sequences(
    frame: pd.DataFrame,
    feature_cols: list[str],
    sequence_length: int,
) -> tuple[np.ndarray, np.ndarray]:
    x_values: list[np.ndarray] = []
    row_indices: list[int] = []
    if len(frame) <= sequence_length:
        return np.empty((0, sequence_length, len(feature_cols))), np.empty((0,))
    values = frame[feature_cols].to_numpy(dtype=np.float32)
    for idx in range(sequence_length, len(frame)):
        x_values.append(values[idx - sequence_length:idx])
        row_indices.append(idx)
    return np.stack(x_values), np.array(row_indices)


def _direction_label(value: float) -> str:
    if value >= 1.5:
        return "BUY"
    if value >= 0.3:
        return "HOLD"
    if value <= -1.5:
        return "SELL"
    return "HOLD"


@dataclass
class BaseModelPrediction:
    model_name: str
    returns: dict[int, float]
    confidence: float
    directional_bias: str
    rationale: str


def _neutral_prediction(model_name: str, rationale: str, confidence: float = 45.0) -> BaseModelPrediction:
    returns = {horizon: 0.0 for horizon in HORIZONS}
    return BaseModelPrediction(model_name, returns, confidence, "HOLD", rationale)


class TreeEnsembleModel:
    name = "Tree Ensemble"

    def __init__(self) -> None:
        self.regressors: dict[int, list[Any]] = {}
        self.classifiers: dict[int, list[Any]] = {}
        self.metrics: dict[str, float] = {}
        self.is_trained = False

    def _build_regressors(self) -> list[Any]:
        models: list[Any] = [
            HistGradientBoostingRegressor(
                random_state=42, max_iter=300, max_depth=4,
                learning_rate=0.04, min_samples_leaf=20,
                l2_regularization=1.0, early_stopping=True,
            )
        ]
        if HAS_XGBOOST:
            models.append(
                XGBRegressor(
                    n_estimators=300,
                    max_depth=4,
                    learning_rate=0.03,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    reg_alpha=0.1,
                    reg_lambda=1.0,
                    min_child_weight=5,
                    random_state=42,
                    tree_method="hist",
                )
            )
        if HAS_LIGHTGBM:
            models.append(
                LGBMRegressor(
                    n_estimators=300, learning_rate=0.03, num_leaves=31,
                    min_child_samples=20, reg_alpha=0.1, reg_lambda=1.0,
                    subsample=0.8, colsample_bytree=0.8,
                    random_state=42, verbose=-1,
                )
            )
        return models

    def _build_classifiers(self) -> list[Any]:
        models: list[Any] = [
            HistGradientBoostingClassifier(
                random_state=42, max_iter=300, max_depth=4,
                learning_rate=0.04, min_samples_leaf=20,
                l2_regularization=1.0, early_stopping=True,
            )
        ]
        if HAS_XGBOOST:
            models.append(
                XGBClassifier(
                    n_estimators=300,
                    max_depth=4,
                    learning_rate=0.03,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    reg_alpha=0.1,
                    reg_lambda=1.0,
                    min_child_weight=5,
                    random_state=42,
                    eval_metric="logloss",
                    tree_method="hist",
                )
            )
        if HAS_LIGHTGBM:
            models.append(
                LGBMClassifier(
                    n_estimators=300, learning_rate=0.03, num_leaves=31,
                    min_child_samples=20, reg_alpha=0.1, reg_lambda=1.0,
                    subsample=0.8, colsample_bytree=0.8,
                    random_state=42, verbose=-1,
                )
            )
        return models

    def train(self, train_frame: pd.DataFrame, feature_cols: list[str]) -> None:
        x = np.nan_to_num(train_frame[feature_cols].to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        for horizon in HORIZONS:
            y_reg = train_frame[f"target_return_{horizon}d"].to_numpy(dtype=np.float32)
            valid_mask = np.isfinite(y_reg)
            models = self._build_regressors()
            for model in models:
                model.fit(x[valid_mask], y_reg[valid_mask])
            self.regressors[horizon] = models

            y_direction = (y_reg > 0).astype(int)
            classifiers = self._build_classifiers()
            for clf in classifiers:
                clf.fit(x[valid_mask], y_direction[valid_mask])
            self.classifiers[horizon] = classifiers

        self.is_trained = True

    def predict_frame(self, frame: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
        x = np.nan_to_num(frame[feature_cols].to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        result = pd.DataFrame(index=frame.index)
        for horizon in HORIZONS:
            result[f"tree_return_{horizon}d"] = 0.0
            result[f"tree_prob_{horizon}d"] = 0.5
        for horizon, models in self.regressors.items():
            if not models:
                continue
            reg_predictions = np.column_stack([model.predict(x) for model in models])
            result[f"tree_return_{horizon}d"] = reg_predictions.mean(axis=1)
            probs = []
            for clf in self.classifiers.get(horizon, []):
                if hasattr(clf, "predict_proba"):
                    probs.append(clf.predict_proba(x)[:, 1])
                else:
                    probs.append(clf.predict(x))
            result[f"tree_prob_{horizon}d"] = np.mean(np.column_stack(probs), axis=1) if probs else 0.5
        return result

    def predict_latest(self, frame: pd.DataFrame, feature_cols: list[str]) -> BaseModelPrediction:
        predicted = self.predict_frame(frame.tail(1), feature_cols).iloc[-1]
        returns = {horizon: float(predicted[f"tree_return_{horizon}d"]) for horizon in HORIZONS}
        confidence = float(np.mean([predicted[f"tree_prob_{horizon}d"] for horizon in HORIZONS]) * 100)
        directional_bias = _direction_label(returns[7])
        rationale = "Tree ensembles learned nonlinear relationships across the 200+ engineered features."
        return BaseModelPrediction(self.name, returns, round(confidence, 2), directional_bias, rationale)


if HAS_TORCH:
    class LSTMForecaster(nn.Module):
        def __init__(self, feature_count: int, hidden_size: int = 64, output_size: int = 3) -> None:
            super().__init__()
            self.lstm = nn.LSTM(feature_count, hidden_size, num_layers=2, batch_first=True, dropout=0.2)
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.GELU(),
                nn.Linear(hidden_size // 2, output_size),
            )

        def forward(self, x: Any) -> Any:
            output, _ = self.lstm(x)
            return self.head(output[:, -1, :])


    class AttentionForecaster(nn.Module):
        def __init__(self, feature_count: int, hidden_size: int = 64, output_size: int = 3) -> None:
            super().__init__()
            self.input_proj = nn.Linear(feature_count, hidden_size)
            self.attention = nn.MultiheadAttention(hidden_size, num_heads=4, batch_first=True)
            self.gru = nn.GRU(hidden_size, hidden_size, batch_first=True)
            self.head = nn.Sequential(
                nn.LayerNorm(hidden_size),
                nn.Linear(hidden_size, hidden_size),
                nn.GELU(),
                nn.Linear(hidden_size, output_size),
            )

        def forward(self, x: Any) -> Any:
            encoded = self.input_proj(x)
            attended, _ = self.attention(encoded, encoded, encoded)
            output, _ = self.gru(attended)
            return self.head(output[:, -1, :])


class SequenceModelBase:
    sequence_length = 30
    name = "Sequence Model"

    def __init__(self) -> None:
        self.scaler = StandardScaler()
        self.model: Any = None
        self.is_trained = False
        self.metrics: dict[str, float] = {}

    def _move_model_to_cpu(self) -> None:
        if HAS_TORCH and self.model is not None and hasattr(self.model, "to"):
            self.model.to(torch.device("cpu"))

    def _prepare_arrays(self, frame: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x_raw = np.nan_to_num(frame[feature_cols].to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        x_scaled = self.scaler.fit_transform(x_raw)
        x_scaled = np.nan_to_num(x_scaled, nan=0.0, posinf=0.0, neginf=0.0)
        scaled_frame = frame.copy()
        scaled_frame[feature_cols] = x_scaled
        sequences, row_indices = _build_sequences(scaled_frame, feature_cols, self.sequence_length)
        sequences = np.nan_to_num(sequences, nan=0.0, posinf=0.0, neginf=0.0)
        targets = np.column_stack(
            [scaled_frame[f"target_return_{horizon}d"].iloc[row_indices].to_numpy(dtype=np.float32) for horizon in HORIZONS]
        )
        targets = np.nan_to_num(targets, nan=0.0, posinf=0.0, neginf=0.0)
        return sequences, targets, row_indices

    def _prepare_prediction_sequences(self, frame: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, np.ndarray]:
        scaled = frame.copy()
        x_raw = np.nan_to_num(frame[feature_cols].to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        x_scaled = np.nan_to_num(self.scaler.transform(x_raw), nan=0.0, posinf=0.0, neginf=0.0)
        scaled[feature_cols] = x_scaled
        sequences, row_indices = _build_sequences(scaled, feature_cols, self.sequence_length)
        sequences = np.nan_to_num(sequences, nan=0.0, posinf=0.0, neginf=0.0)
        return sequences, row_indices

    def train(self, train_frame: pd.DataFrame, feature_cols: list[str]) -> None:
        raise NotImplementedError

    def predict_frame(self, frame: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
        result = pd.DataFrame(index=frame.index)
        for horizon in HORIZONS:
            result[f"{self.output_prefix}_return_{horizon}d"] = 0.0
        if not self.is_trained or len(frame) <= self.sequence_length:
            return result
        sequences, row_indices = self._prepare_prediction_sequences(frame, feature_cols)
        if len(sequences) == 0:
            return result
        if HAS_TORCH:
            device = _torch_device()
            self.model.to(device)
            self.model.eval()
            # Predict in chunks: a single forward pass over the full history
            # allocates activations for every sequence at once and OOMs the GPU.
            batch_size = _env_int("NEPSE_INFERENCE_BATCH_SIZE", 1024)
            predicted_batches = []
            with torch.no_grad():
                for start in range(0, len(sequences), batch_size):
                    batch = torch.as_tensor(
                        sequences[start : start + batch_size], dtype=torch.float32, device=device
                    )
                    predicted_batches.append(self.model(batch).detach().cpu().numpy())
            predicted = np.concatenate(predicted_batches, axis=0)
        else:
            predicted = self.model.predict(sequences.reshape(len(sequences), -1))
        for horizon_index, horizon in enumerate(HORIZONS):
            result.loc[result.index[row_indices], f"{self.output_prefix}_return_{horizon}d"] = predicted[:, horizon_index]
        return result

    def predict_latest(self, frame: pd.DataFrame, feature_cols: list[str]) -> BaseModelPrediction:
        returns = {horizon: 0.0 for horizon in HORIZONS}
        if self.is_trained and len(frame) > self.sequence_length:
            latest_window = frame.tail(self.sequence_length + 1).copy()
            sequences, _ = self._prepare_prediction_sequences(latest_window, feature_cols)
            if len(sequences) > 0:
                latest_sequence = sequences[-1:]
                if HAS_TORCH:
                    device = _torch_device()
                    self.model.to(device)
                    self.model.eval()
                    with torch.no_grad():
                        latest_tensor = torch.as_tensor(latest_sequence, dtype=torch.float32, device=device)
                        predicted = self.model(latest_tensor).detach().cpu().numpy()[0]
                else:
                    predicted = self.model.predict(latest_sequence.reshape(len(latest_sequence), -1))[0]
                returns = {
                    horizon: float(predicted[horizon_index])
                    for horizon_index, horizon in enumerate(HORIZONS)
                }
        confidence = float(np.clip(55 + (1 / (1 + np.std(list(returns.values())))) * 20, 0, 100))
        directional_bias = _direction_label(returns[7])
        return BaseModelPrediction(self.name, returns, round(confidence, 2), directional_bias, self.rationale)


class SequenceLSTMModel(SequenceModelBase):
    name = "LSTM Sequence Model"
    output_prefix = "lstm"
    rationale = "LSTM focuses on temporal order, momentum persistence, and nonlinear cycle memory."

    def train(self, train_frame: pd.DataFrame, feature_cols: list[str]) -> None:
        sequences, targets, _ = self._prepare_arrays(train_frame, feature_cols)
        if len(sequences) == 0:
            return
        if HAS_TORCH:
            device = _torch_device()
            self.model = LSTMForecaster(
                len(feature_cols),
                hidden_size=_env_int("NEPSE_LSTM_HIDDEN_SIZE", 128),
            ).to(device)
            optimizer = torch.optim.AdamW(self.model.parameters(), lr=5e-4, weight_decay=1e-4)
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=_env_int("NEPSE_LSTM_EPOCHS", 80)
            )
            loss_fn = nn.SmoothL1Loss()
            dataset = TensorDataset(
                torch.as_tensor(sequences, dtype=torch.float32),
                torch.as_tensor(targets, dtype=torch.float32),
            )
            loader = DataLoader(
                dataset,
                batch_size=_env_int("NEPSE_SEQUENCE_BATCH_SIZE", 128),
                shuffle=True,
                pin_memory=device.type == "cuda",
                drop_last=True,
            )
            self.model.train()
            best_loss = float("inf")
            patience_count = 0
            for epoch in range(_env_int("NEPSE_LSTM_EPOCHS", 80)):
                epoch_loss = 0.0
                for batch_x, batch_y in loader:
                    batch_x = batch_x.to(device, non_blocking=True)
                    batch_y = batch_y.to(device, non_blocking=True)
                    optimizer.zero_grad()
                    prediction = self.model(batch_x)
                    loss = loss_fn(prediction, batch_y)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                    optimizer.step()
                    _sync_xla(device)
                    epoch_loss += loss.item()
                scheduler.step()
                avg_loss = epoch_loss / max(1, len(loader))
                if avg_loss < best_loss:
                    best_loss = avg_loss
                    patience_count = 0
                else:
                    patience_count += 1
                if patience_count >= 12:
                    break
        else:
            flattened = np.nan_to_num(sequences.reshape(len(sequences), -1), nan=0.0, posinf=0.0, neginf=0.0)
            self.model = MLPRegressor(hidden_layer_sizes=(64, 32), random_state=42, max_iter=120)
            self.model.fit(flattened, targets)
        self.is_trained = True


class TemporalFusionStyleModel(SequenceModelBase):
    name = "Temporal Fusion Transformer"
    output_prefix = "tft"
    rationale = "Temporal-fusion style attention emphasizes context switching and multi-horizon forecasting."

    def train(self, train_frame: pd.DataFrame, feature_cols: list[str]) -> None:
        sequences, targets, _ = self._prepare_arrays(train_frame, feature_cols)
        if len(sequences) == 0:
            return
        if HAS_TORCH:
            device = _torch_device()
            self.model = AttentionForecaster(
                len(feature_cols),
                hidden_size=_env_int("NEPSE_TFT_HIDDEN_SIZE", 128),
            ).to(device)
            optimizer = torch.optim.AdamW(self.model.parameters(), lr=5e-4, weight_decay=1e-4)
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer, T_max=_env_int("NEPSE_TFT_EPOCHS", 80)
            )
            loss_fn = nn.SmoothL1Loss()
            dataset = TensorDataset(
                torch.as_tensor(sequences, dtype=torch.float32),
                torch.as_tensor(targets, dtype=torch.float32),
            )
            loader = DataLoader(
                dataset,
                batch_size=_env_int("NEPSE_SEQUENCE_BATCH_SIZE", 128),
                shuffle=True,
                pin_memory=device.type == "cuda",
                drop_last=True,
            )
            self.model.train()
            best_loss = float("inf")
            patience_count = 0
            for epoch in range(_env_int("NEPSE_TFT_EPOCHS", 80)):
                epoch_loss = 0.0
                for batch_x, batch_y in loader:
                    batch_x = batch_x.to(device, non_blocking=True)
                    batch_y = batch_y.to(device, non_blocking=True)
                    optimizer.zero_grad()
                    prediction = self.model(batch_x)
                    loss = loss_fn(prediction, batch_y)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                    optimizer.step()
                    _sync_xla(device)
                    epoch_loss += loss.item()
                scheduler.step()
                avg_loss = epoch_loss / max(1, len(loader))
                if avg_loss < best_loss:
                    best_loss = avg_loss
                    patience_count = 0
                else:
                    patience_count += 1
                if patience_count >= 12:
                    break
        else:
            flattened = np.nan_to_num(sequences.reshape(len(sequences), -1), nan=0.0, posinf=0.0, neginf=0.0)
            self.model = RandomForestRegressor(n_estimators=60, random_state=42, n_jobs=-1)
            self.model.fit(flattened, targets)
        self.is_trained = True


class ReinforcementLearningStrategyModel:
    name = "PPO Strategy Agent"

    def __init__(self, transaction_cost_bps: float = 75.0) -> None:
        self.transaction_cost_bps = transaction_cost_bps
        self.model: Any = None
        self.feature_cols: list[str] = []
        self.is_trained = False

    def _prepare_for_save(self) -> None:
        if not HAS_PPO or self.model is None:
            return
        for attribute in ("env", "_vec_normalize_env"):
            if hasattr(self.model, attribute):
                setattr(self.model, attribute, None)

    def train(self, train_frame: pd.DataFrame, feature_cols: list[str]) -> None:
        self.feature_cols = list(feature_cols)
        if not HAS_PPO or len(train_frame) < 150:
            self.is_trained = True
            return

        class TradingEnv(gym.Env):
            metadata = {"render_modes": []}

            def __init__(self, frame: pd.DataFrame, columns: list[str], cost_bps: float) -> None:
                super().__init__()
                self.frame = frame.reset_index(drop=True)
                self.columns = columns
                self.cost = cost_bps / 10000
                self.index = 0
                self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(len(columns),), dtype=np.float32)
                self.action_space = gym.spaces.Discrete(3)

            def reset(self, *, seed: Optional[int] = None, options: Optional[dict[str, Any]] = None) -> tuple[np.ndarray, dict[str, Any]]:
                super().reset(seed=seed)
                self.index = 0
                return self.frame.loc[self.index, self.columns].to_numpy(dtype=np.float32), {}

            def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
                current_return = float(self.frame.loc[self.index, "return_1d"])
                position = {0: -1.0, 1: 0.0, 2: 1.0}[int(action)]
                reward = position * current_return - abs(position) * self.cost
                self.index += 1
                terminated = self.index >= len(self.frame) - 1
                observation = self.frame.loc[min(self.index, len(self.frame) - 1), self.columns].to_numpy(dtype=np.float32)
                return observation, reward, terminated, False, {}

        env = TradingEnv(train_frame, feature_cols, self.transaction_cost_bps)
        self.model = PPO(
            "MlpPolicy",
            env,
            verbose=0,
            n_steps=_env_int("NEPSE_PPO_N_STEPS", 256),
            batch_size=_env_int("NEPSE_PPO_BATCH_SIZE", 256),
            learning_rate=3e-4,
            device=os.getenv("NEPSE_PPO_DEVICE", "cpu"),
        )
        self.model.learn(total_timesteps=_env_int("NEPSE_PPO_TIMESTEPS", 100_000))
        self._prepare_for_save()
        self.is_trained = True

    def predict_frame(self, frame: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
        result = pd.DataFrame(index=frame.index)
        for horizon in HORIZONS:
            result[f"rl_return_{horizon}d"] = 0.0
        if not self.is_trained:
            return result
        volatility = frame["volatility_20d"] if "volatility_20d" in frame.columns else frame["return_1d"].rolling(20, min_periods=2).std(ddof=0).fillna(0.02)
        volatility = volatility.fillna(0.02)
        actions = []
        if HAS_PPO and self.model is not None:
            for _, row in frame.iterrows():
                action, _ = self.model.predict(row[feature_cols].to_numpy(dtype=np.float32), deterministic=True)
                actions.append({0: -1.0, 1: 0.0, 2: 1.0}[int(action)])
        else:
            actions = np.where(
                (frame.get("ema_9", frame["close"]) > frame.get("ema_21", frame["close"])) & (frame.get("macd_histogram", 0.0) > 0),
                1.0,
                np.where((frame.get("ema_9", frame["close"]) < frame.get("ema_21", frame["close"])) & (frame.get("macd_histogram", 0.0) < 0), -1.0, 0.0),
            ).tolist()
        for horizon in HORIZONS:
            expected_move = volatility * np.sqrt(horizon)
            result[f"rl_return_{horizon}d"] = np.array(actions) * expected_move * 100
        return result

    def predict_latest(self, frame: pd.DataFrame, feature_cols: list[str]) -> BaseModelPrediction:
        predicted = self.predict_frame(frame.tail(1), feature_cols).iloc[-1]
        returns = {horizon: float(predicted[f"rl_return_{horizon}d"]) for horizon in HORIZONS}
        action_strength = abs(returns[7])
        confidence = float(np.clip(45 + action_strength * 3, 0, 100))
        directional_bias = _direction_label(returns[7])
        rationale = "RL agent optimizes buy/hold/sell timing under transaction-cost-aware reward shaping."
        return BaseModelPrediction(self.name, returns, round(confidence, 2), directional_bias, rationale)


class NewsSentimentModel:
    name = "News Sentiment Model"

    POSITIVE_TOKENS = {
        "strong",
        "growth",
        "beat",
        "upgrade",
        "expansion",
        "profit",
        "bullish",
        "improves",
        "improvement",
        "renewal",
        "लाभ",
        "बृद्धि",
        "सकारात्मक",
        "मुनाफा",
    }
    NEGATIVE_TOKENS = {
        "loss",
        "decline",
        "downgrade",
        "fraud",
        "default",
        "weak",
        "bearish",
        "delay",
        "probe",
        "penalty",
        "घाटा",
        "कमजोर",
        "नकारात्मक",
        "असुली",
    }

    def score_articles(self, articles: pd.DataFrame) -> float:
        if articles.empty:
            return 0.0
        scores: list[float] = []
        for _, row in articles.iterrows():
            text = f"{row.get('title', '')} {row.get('body', '')}".lower()
            token_score = sum(token in text for token in self.POSITIVE_TOKENS) - sum(token in text for token in self.NEGATIVE_TOKENS)
            base = float(row.get("sentiment_score", 0.0) or 0.0)
            scores.append(base + token_score * 0.15)
        return float(np.clip(np.mean(scores), -1.0, 1.0))

    def predict_latest(self, sentiment_value: float) -> BaseModelPrediction:
        bias = np.clip(sentiment_value, -1.0, 1.0)
        returns = {
            7: float(bias * 4.0),
            30: float(bias * 8.0),
            90: float(bias * 12.0),
        }
        confidence = float(45 + abs(bias) * 40)
        directional_bias = _direction_label(returns[7])
        rationale = "Sentiment model fuses Nepali and English financial tone with stored article scores."
        return BaseModelPrediction(self.name, returns, round(confidence, 2), directional_bias, rationale)


class ContextualMetaLearner:
    def __init__(self) -> None:
        self.return_models: dict[int, Ridge] = {}
        self.direction_model = LogisticRegression(max_iter=500)
        self.context_columns: list[str] = []
        self.feature_names: list[str] = []
        self.is_trained = False

    def train(self, base_frame: pd.DataFrame, context_frame: pd.DataFrame, target_frame: pd.DataFrame) -> None:
        self.context_columns = [column for column in context_frame.columns if pd.api.types.is_numeric_dtype(context_frame[column])]
        features = pd.concat([base_frame, context_frame[self.context_columns]], axis=1).fillna(0.0)
        self.feature_names = list(features.columns)
        x = np.nan_to_num(features.to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        for horizon in HORIZONS:
            model = Ridge(alpha=1.0)
            y = np.nan_to_num(target_frame[f"target_return_{horizon}d"].to_numpy(dtype=np.float32), nan=0.0)
            model.fit(x, y)
            self.return_models[horizon] = model
        self.direction_model.fit(x, (target_frame["target_return_7d"] > 0).astype(int))
        self.is_trained = True

    def predict(self, base_row: pd.DataFrame, context_row: pd.DataFrame) -> tuple[dict[int, float], float]:
        features = pd.concat([base_row, context_row[self.context_columns]], axis=1).fillna(0.0)
        features = features.reindex(columns=self.feature_names, fill_value=0.0)
        x = np.nan_to_num(features.to_numpy(dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        returns = {
            horizon: float(model.predict(x)[0])
            for horizon, model in self.return_models.items()
        }
        probability = float(self.direction_model.predict_proba(x)[0][1]) if self.is_trained else 0.5
        return returns, probability * 100


class AutonomousModelSuite:
    """Owns all model families and the contextual stacking layer."""
    live_return_caps = {
        7: 12.0,
        30: 20.0,
        90: 32.0,
    }

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.tree = TreeEnsembleModel()
        self.lstm = SequenceLSTMModel()
        self.tft = TemporalFusionStyleModel()
        self.rl = ReinforcementLearningStrategyModel(self.settings.transaction_cost_bps)
        self.sentiment = NewsSentimentModel()
        self.meta = ContextualMetaLearner()
        self.feature_cols: list[str] = []
        self.context_cols = [
            "rsi_14",
            "adx_14",
            "volatility_20d",
            "return_20d",
            "sentiment_mean",
            "market_return_1d",
            "beta_20d",
        ]
        self.metrics: dict[str, float] = {}
        self.model_version = "bootstrap"
        self.last_trained_at: Optional[datetime] = None

    @property
    def artifact_path(self) -> Path:
        return Path(self.settings.model_artifact_dir) / "autonomous_model_suite.joblib"

    def save(self) -> None:
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        self.lstm._move_model_to_cpu()
        self.tft._move_model_to_cpu()
        self.rl._prepare_for_save()
        joblib.dump(self, self.artifact_path)

    @classmethod
    def load(cls, settings: Optional[Settings] = None) -> "AutonomousModelSuite":
        settings = settings or get_settings()
        path = Path(settings.model_artifact_dir) / "autonomous_model_suite.joblib"
        if path.exists():
            try:
                return joblib.load(path)
            except Exception as exc:
                logger.warning("Unable to load model suite from %s: %s", path, exc)
        return cls(settings=settings)

    def train(self, symbol_feature_frames: dict[str, pd.DataFrame]) -> None:
        dataset = pd.concat(
            [frame for frame in symbol_feature_frames.values() if not frame.empty],
            ignore_index=True,
        )
        dataset = dataset.sort_values("date").reset_index(drop=True)
        dataset = dataset.replace([np.inf, -np.inf], np.nan).dropna(subset=["target_return_7d", "target_return_30d", "target_return_90d"])
        max_rows = _env_int("NEPSE_TRAINING_MAX_ROWS", 60_000)
        if len(dataset) > max_rows:
            # Keep recent data but also sample from older history for diversity
            recent = dataset.tail(int(max_rows * 0.75))
            older = dataset.iloc[: len(dataset) - int(max_rows * 0.75)]
            sampled_older = older.sample(
                n=min(len(older), int(max_rows * 0.25)), random_state=42
            ) if len(older) > 0 else pd.DataFrame()
            dataset = pd.concat([sampled_older, recent], ignore_index=True).sort_values("date").reset_index(drop=True)
        if len(dataset) < 120:
            logger.warning("Insufficient data to train the autonomous model suite.")
            return

        self.feature_cols = feature_columns(dataset)
        split_index = int(len(dataset) * 0.8)
        train_frame = dataset.iloc[:split_index].copy()
        valid_frame = dataset.iloc[split_index:].copy()

        self.tree.train(train_frame, self.feature_cols)
        self.lstm.train(train_frame, self.feature_cols)
        self.tft.train(train_frame, self.feature_cols)
        self.rl.train(train_frame.fillna(0.0), self.feature_cols)

        base_valid = self._base_prediction_frame(valid_frame)
        sentiment_columns = [column for column in self.context_cols if column in valid_frame.columns]
        self.meta.train(base_valid, valid_frame[sentiment_columns], valid_frame)

        meta_predictions, probabilities = self._meta_predict_frame(valid_frame, base_valid)
        y_true_7d = (valid_frame["target_return_7d"] > 0).values
        y_pred_7d = (meta_predictions["meta_return_7d"] > 0).values
        y_true_30d = valid_frame["target_return_30d"].values
        y_pred_30d = meta_predictions["meta_return_30d"].values
        # Precision-like metric: of the signals we'd BUY (top 30%), how many were right?
        top_30_idx = np.argsort(meta_predictions["meta_return_7d"].values)[-int(len(meta_predictions) * 0.30):]
        precision_top30 = float(np.mean(y_true_7d[top_30_idx])) * 100 if len(top_30_idx) > 0 else 0.0
        self.metrics = {
            "accuracy_7d": round(accuracy_score(y_true_7d, y_pred_7d) * 100, 2),
            "precision_top30pct_7d": round(precision_top30, 2),
            "mae_7d": round(mean_absolute_error(valid_frame["target_return_7d"], meta_predictions["meta_return_7d"]), 4),
            "r2_7d": round(max(-1.0, r2_score(valid_frame["target_return_7d"], meta_predictions["meta_return_7d"])), 4),
            "r2_30d": round(max(-1.0, r2_score(y_true_30d, y_pred_30d)), 4),
            "confidence_mean": round(float(np.mean(probabilities)), 2),
            "validation_samples": len(valid_frame),
            "training_samples": len(train_frame),
        }
        self.model_version = datetime.utcnow().strftime("ensemble-%Y%m%d%H%M%S")
        self.last_trained_at = datetime.utcnow()
        self.save()

    def _base_prediction_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        components = [
            self.tree.predict_frame(frame, self.feature_cols),
            self.lstm.predict_frame(frame, self.feature_cols),
            self.tft.predict_frame(frame, self.feature_cols),
            self.rl.predict_frame(frame.fillna(0.0), self.feature_cols),
        ]
        result = pd.concat(components, axis=1)
        sentiment_mean = frame["sentiment_mean"] if "sentiment_mean" in frame.columns else pd.Series(np.zeros(len(frame)), index=frame.index)
        result["sentiment_return_7d"] = sentiment_mean * 4.0
        result["sentiment_return_30d"] = sentiment_mean * 8.0
        result["sentiment_return_90d"] = sentiment_mean * 12.0
        return result.fillna(0.0)

    def _meta_predict_frame(self, frame: pd.DataFrame, base_frame: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
        context_frame = frame[[column for column in self.context_cols if column in frame.columns]].copy()
        predictions = pd.DataFrame(index=frame.index)
        probabilities = []
        for index in frame.index:
            base_row = base_frame.loc[[index]]
            context_row = context_frame.loc[[index]]
            returns, probability = self.meta.predict(base_row, context_row)
            probabilities.append(probability)
            for horizon in HORIZONS:
                predictions.loc[index, f"meta_return_{horizon}d"] = returns[horizon]
        return predictions.fillna(0.0), np.array(probabilities)

    def _prepare_prediction_frame(self, feature_frame: pd.DataFrame) -> pd.DataFrame:
        if feature_frame.empty:
            raise ValueError("Feature frame is empty.")
        if not self.feature_cols:
            self.feature_cols = feature_columns(feature_frame)
        prepared_frame = feature_frame.copy()
        required_columns = set(self.feature_cols) | set(self.context_cols)
        for column in required_columns:
            if column not in prepared_frame.columns:
                prepared_frame[column] = 0.0
        return prepared_frame

    def _build_vote_payload(self, votes: list[BaseModelPrediction]) -> list[dict[str, Any]]:
        return [
            {
                "model_name": vote.model_name,
                "confidence": vote.confidence,
                "predicted_return_7d": round(vote.returns[7], 4),
                "predicted_return_30d": round(vote.returns[30], 4),
                "predicted_return_90d": round(vote.returns[90], 4),
                "directional_bias": vote.directional_bias,
                "rationale": vote.rationale,
            }
            for vote in votes
        ]

    def _finalize_confidence(self, votes: list[BaseModelPrediction], base_confidence: float) -> float:
        agreement = 1 - np.std([vote.returns[7] for vote in votes]) / max(
            np.mean(np.abs([vote.returns[7] for vote in votes])) + 1e-6,
            1.0,
        )
        return float(np.clip(base_confidence * 0.7 + agreement * 30, 0, 100))

    def _clip_expected_returns(self, expected_returns: dict[int, float]) -> dict[int, float]:
        return {
            horizon: float(
                np.clip(
                    expected_returns.get(horizon, 0.0),
                    -self.live_return_caps[horizon],
                    self.live_return_caps[horizon],
                )
            )
            for horizon in HORIZONS
        }

    def predict_latest(self, feature_frame: pd.DataFrame, sentiment_value: float) -> dict[str, Any]:
        prepared_frame = self._prepare_prediction_frame(feature_frame)

        tree_vote = self.tree.predict_latest(prepared_frame, self.feature_cols)
        lstm_vote = self.lstm.predict_latest(prepared_frame, self.feature_cols) if self.lstm.is_trained else _neutral_prediction(self.lstm.name, self.lstm.rationale)
        tft_vote = self.tft.predict_latest(prepared_frame, self.feature_cols) if self.tft.is_trained else _neutral_prediction(self.tft.name, self.tft.rationale)
        rl_vote = self.rl.predict_latest(prepared_frame.fillna(0.0), self.feature_cols)
        sentiment_vote = self.sentiment.predict_latest(sentiment_value)
        votes = [tree_vote, lstm_vote, tft_vote, rl_vote, sentiment_vote]

        base_row = pd.DataFrame(
            {
                "tree_return_7d": [tree_vote.returns[7]],
                "tree_return_30d": [tree_vote.returns[30]],
                "tree_return_90d": [tree_vote.returns[90]],
                "lstm_return_7d": [lstm_vote.returns[7]],
                "lstm_return_30d": [lstm_vote.returns[30]],
                "lstm_return_90d": [lstm_vote.returns[90]],
                "tft_return_7d": [tft_vote.returns[7]],
                "tft_return_30d": [tft_vote.returns[30]],
                "tft_return_90d": [tft_vote.returns[90]],
                "rl_return_7d": [rl_vote.returns[7]],
                "rl_return_30d": [rl_vote.returns[30]],
                "rl_return_90d": [rl_vote.returns[90]],
                "sentiment_return_7d": [sentiment_vote.returns[7]],
                "sentiment_return_30d": [sentiment_vote.returns[30]],
                "sentiment_return_90d": [sentiment_vote.returns[90]],
            }
        )
        context_columns = [column for column in self.context_cols if column in prepared_frame.columns]
        context_row = prepared_frame[context_columns].tail(1).copy()

        if self.meta.is_trained:
            expected_returns, confidence = self.meta.predict(base_row, context_row)
        else:
            weights = np.array([0.28, 0.2, 0.18, 0.2, 0.14])
            expected_returns = {
                horizon: float(np.dot(weights, [vote.returns[horizon] for vote in votes]))
                for horizon in HORIZONS
            }
            confidence = float(np.mean([vote.confidence for vote in votes]))

        vote_payload = self._build_vote_payload(votes)
        confidence = self._finalize_confidence(votes, confidence)
        return {
            "expected_returns": {horizon: round(expected_returns[horizon], 4) for horizon in HORIZONS},
            "confidence": round(confidence, 2),
            "votes": vote_payload,
            "historical_accuracy": self.metrics.get("accuracy_7d", 58.0),
            "model_version": self.model_version,
        }

    def predict_latest_live(self, feature_frame: pd.DataFrame, sentiment_value: float) -> dict[str, Any]:
        prepared_frame = self._prepare_prediction_frame(feature_frame)

        tree_vote = self.tree.predict_latest(prepared_frame, self.feature_cols)
        lstm_vote = _neutral_prediction(
            self.lstm.name,
            f"{self.lstm.rationale} Live scoring currently bypasses this sequence vote to avoid PyTorch runtime stalls.",
            confidence=35.0,
        )
        tft_vote = _neutral_prediction(
            self.tft.name,
            f"{self.tft.rationale} Live scoring currently bypasses this sequence vote to avoid PyTorch runtime stalls.",
            confidence=35.0,
        )
        rl_vote = self.rl.predict_latest(prepared_frame.fillna(0.0), self.feature_cols)
        sentiment_vote = self.sentiment.predict_latest(sentiment_value)
        votes = [tree_vote, lstm_vote, tft_vote, rl_vote, sentiment_vote]

        live_weights = np.array([0.58, 0.0, 0.0, 0.24, 0.18])
        expected_returns = {
            horizon: float(np.dot(live_weights, [vote.returns[horizon] for vote in votes]))
            for horizon in HORIZONS
        }
        expected_returns = self._clip_expected_returns(expected_returns)
        base_confidence = float(
            np.average(
                [tree_vote.confidence, rl_vote.confidence, sentiment_vote.confidence],
                weights=[0.58, 0.24, 0.18],
            )
        )
        confidence = self._finalize_confidence(votes, base_confidence)

        return {
            "expected_returns": {horizon: round(expected_returns[horizon], 4) for horizon in HORIZONS},
            "confidence": round(confidence, 2),
            "votes": self._build_vote_payload(votes),
            "historical_accuracy": self.metrics.get("accuracy_7d", 58.0),
            "model_version": self.model_version,
            "stability_mode": "live_fallback",
        }
