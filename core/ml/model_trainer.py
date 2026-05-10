# /core/ml/model_trainer.py

import json
import time
import numpy as np
import tensorflow as tf

from sklearn.model_selection import train_test_split

from redis_store import redis_client


# --------------------------------------------------
# SEARCH SPACE (RANDOM SEARCH CONFIG)
# --------------------------------------------------
HYPERPARAM_SPACE = {
    "hidden_units": [4, 8, 16, 32],
    "activation": ["relu", "tanh"],
    "learning_rate": [0.001, 0.0005, 0.0001],
    "batch_size": [8, 16, 32],
    "epochs": [10, 25, 50],
    "optimizer": ["adam", "rmsprop"]
}


# --------------------------------------------------
# MODEL BUILDER
# --------------------------------------------------
def build_model(input_dim, config):

    model = tf.keras.Sequential([
        tf.keras.layers.Dense(
            config["hidden_units"],
            activation=config["activation"],
            input_shape=(input_dim,)
        ),
        tf.keras.layers.Dense(4, activation="softmax")
    ])

    if config["optimizer"] == "adam":
        optimizer = tf.keras.optimizers.Adam(
            learning_rate=config["learning_rate"]
        )
    else:
        optimizer = tf.keras.optimizers.RMSprop(
            learning_rate=config["learning_rate"]
        )

    model.compile(
        optimizer=optimizer,
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )

    return model


# --------------------------------------------------
# RANDOM CONFIG SAMPLER
# --------------------------------------------------
def sample_config():

    return {
        "hidden_units": np.random.choice(HYPERPARAM_SPACE["hidden_units"]),
        "activation": np.random.choice(HYPERPARAM_SPACE["activation"]),
        "learning_rate": np.random.choice(HYPERPARAM_SPACE["learning_rate"]),
        "batch_size": np.random.choice(HYPERPARAM_SPACE["batch_size"]),
        "epochs": np.random.choice(HYPERPARAM_SPACE["epochs"]),
        "optimizer": np.random.choice(HYPERPARAM_SPACE["optimizer"])
    }


# --------------------------------------------------
# TRAIN SINGLE MODEL
# --------------------------------------------------
def train_candidate(X_train, y_train, X_val, y_val, config):

    model = build_model(
        input_dim=X_train.shape[1],
        config=config
    )

    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=config["epochs"],
        batch_size=config["batch_size"],
        verbose=0
    )

    val_acc = history.history["val_accuracy"][-1]
    val_loss = history.history["val_loss"][-1]

    return model, val_acc, val_loss


# --------------------------------------------------
# MAIN TRAINING LOOP (RANDOM SEARCH)
# --------------------------------------------------
def train_model(features, labels, search_trials=10):

    X_train, X_val, y_train, y_val = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42
    )

    best_model = None
    best_config = None
    best_score = -1

    best_metrics = {}

    for i in range(search_trials):

        config = sample_config()

        print(f"[TRAIN] Trial {i+1}/{search_trials} -> {config}")

        model, val_acc, val_loss = train_candidate(
            X_train,
            y_train,
            X_val,
            y_val,
            config
        )

        score = val_acc - val_loss

        if score > best_score:

            best_score = score
            best_model = model
            best_config = config

            best_metrics = {
                "val_accuracy": float(val_acc),
                "val_loss": float(val_loss)
            }

    return best_model, best_config, best_metrics


# --------------------------------------------------
# EXPORT TO TFLITE
# --------------------------------------------------
def export_tflite(model):

    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    tflite_model = converter.convert()

    path = "/app/models/risk_model.tflite"

    with open(path, "wb") as f:
        f.write(tflite_model)

    return path


# --------------------------------------------------
# SAVE METADATA
# --------------------------------------------------
def save_metadata(config, metrics):

    metadata = {
        "model_version": f"v{int(time.time())}",
        "trained_at": int(time.time()),
        "architecture": {
            "layers": 1,
            "hidden_units": config["hidden_units"],
            "activation": config["activation"]
        },
        "optimizer": config["optimizer"],
        "learning_rate": config["learning_rate"],
        "batch_size": config["batch_size"],
        "epochs": config["epochs"],
        "metrics": metrics,
        "export_format": "tflite"
    }

    # ---------------- REDIS ----------------
    redis_client.set(
        "model:latest",
        json.dumps(metadata)
    )

    redis_client.rpush(
        "model:history",
        json.dumps(metadata)
    )

    redis_client.set(
        "model:best_config",
        json.dumps(config)
    )

    redis_client.set(
        "model:metrics",
        json.dumps(metrics)
    )

    return metadata


# --------------------------------------------------
# FULL PIPELINE ENTRYPOINT
# --------------------------------------------------
def run_training(features, labels):

    print("[ML] Starting training pipeline...")

    model, config, metrics = train_model(
        features,
        labels,
        search_trials=10
    )

    print("[ML] Best model selected:", config)

    export_path = export_tflite(model)

    print("[ML] Model exported:", export_path)

    metadata = save_metadata(config, metrics)

    print("[ML] Metadata saved to Redis")

    return {
        "model_path": export_path,
        "metadata": metadata
    }
