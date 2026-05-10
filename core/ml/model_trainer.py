# /core/ml/model_trainer.py

import numpy as np
import tensorflow as tf

from sklearn.linear_model import LogisticRegression


def train_model(features, labels):

    model = LogisticRegression(
        multi_class="multinomial",
        max_iter=1000
    )

    model.fit(features, labels)

    return model


def export_tflite():

    model = tf.keras.Sequential([
        tf.keras.layers.Dense(
            4,
            activation="softmax",
            input_shape=(2,)
        )
    ])

    converter = tf.lite.TFLiteConverter.from_keras_model(
        model
    )

    tflite_model = converter.convert()

    with open(
        "/app/models/risk_model.tflite",
        "wb"
    ) as f:
        f.write(tflite_model)
