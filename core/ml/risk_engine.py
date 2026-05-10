# /core/ml/risk_engine.py


def classify_risk(score):

    if score < 0.25:
        return "Low"

    elif score < 0.5:
        return "Medium"

    elif score < 0.75:
        return "High"

    return "Critical"


def compute_probability(score):

    probability = min(
        max(score, 0.0),
        1.0
    )

    return probability
