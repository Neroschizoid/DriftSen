import joblib
import pandas as pd
import os
from utils.logger import logger

model = None
model_features = None

def load_model():
    global model, model_features
    if model is None:
        model_path = os.path.join(os.path.dirname(__file__), "../../../ml/models/model.pkl")
        model = joblib.load(model_path)
        model_features = model.feature_names_in_
        logger.info("Model loaded successfully.")

def predict(input_data: dict | list):
    global model, model_features
    if model is None:
        raise RuntimeError("Model is not loaded.")
    
    if isinstance(input_data, list):
        # Infer column names if anonymous list passed, padding up to model_features size or slicing
        # This handles the raw list of values pseudo-code case safely
        padded_features = input_data + [0] * max(0, len(model_features) - len(input_data))
        padded_features = padded_features[:len(model_features)]
        df = pd.DataFrame([padded_features], columns=model_features)
    else:
        df = pd.DataFrame([input_data])
        df = pd.get_dummies(df)
        df = df.reindex(columns=model_features, fill_value=0)
    
    pred = int(model.predict(df)[0])
    prob = model.predict_proba(df)[0]
    conf = float(prob[1]) if pred == 1 else float(prob[0])
    
    return pred, conf
