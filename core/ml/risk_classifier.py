# /core/ml/risk_classifier.py

from config import (
    DRIFT_THRESHOLD_HIGH,
    DRIFT_THRESHOLD_LOW,
    DRIFT_THRESHOLD_MEDIUM,
    RISK_CLASSES
)

# --------------------------------------------------
# RULES-BASED RISK CLASSIFIER
# --------------------------------------------------
# Replaces the former Keras classifier (Phase 4 dropped Keras + TFLite).
# Deterministic: same drift score -> same class.
#
# Each class has a [lower, upper) band. The last band is open-ended.
# Confidence is the normalized distance from the drift score to the
# nearest band edge, mapped onto [0.5, 1.0]. It is a rule margin,
# not a learned probability.
# --------------------------------------------------

BANDS = [
    (0.0, DRIFT_THRESHOLD_LOW),
    (DRIFT_THRESHOLD_LOW, DRIFT_THRESHOLD_MEDIUM),
    (DRIFT_THRESHOLD_MEDIUM, DRIFT_THRESHOLD_HIGH),
    (DRIFT_THRESHOLD_HIGH, None)
]


def classify_risk(drift_score):
    """Map a drift score to (label, confidence)."""

    score = float(drift_score)

    label_index = len(BANDS) - 1

    for index, (_, upper) in enumerate(BANDS):
        if upper is None or score < upper:
            label_index = index
            break

    return RISK_CLASSES[label_index], _band_margin(score, label_index)


def _band_margin(score, label_index):
    lower, upper = BANDS[label_index]

    if upper is None:
        distance = min(
            max(score - lower, 0.0),
            1.0
        )

        margin = distance

    else:
        band = upper - lower

        if band <= 0:
            return 1.0

        distance = min(
            score - lower,
            upper - score
        )

        margin = max(distance, 0.0) / band

    return round(
        0.5 + (margin * 0.5),
        4
    )
