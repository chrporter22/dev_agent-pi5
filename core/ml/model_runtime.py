# /core/ml/model_runtime.py

import numpy as np
import tflite_runtime.interpreter as tflite

from config import MODEL_PATH


class RiskModel:

    def __init__(self):
        
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"Missing model: {MODEL_PATH}"
            )
        
        self.interpreter = tflite.Interpreter(
            model_path=MODEL_PATH
        )

        self.interpreter.allocate_tensors()

        self.input_details = (
            self.interpreter.get_input_details()
        )

        self.output_details = (
            self.interpreter.get_output_details()
        )

    def predict(self, features):

        tensor = np.array(
            [features],
            dtype=np.float32
        )

        self.interpreter.set_tensor(
            self.input_details[0]["index"],
            tensor
        )

        self.interpreter.invoke()

        output = self.interpreter.get_tensor(
            self.output_details[0]["index"]
        )

        prediction = int(np.argmax(output))
        confidence = float(np.max(output))

        return {
            "prediction": prediction,
            "confidence": confidence
        }
