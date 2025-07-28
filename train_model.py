import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder
import joblib


df = pd.read_csv("fraud_dataset_balanced.csv")

le = LabelEncoder()
df["Location"] = le.fit_transform(df["Location"])

X = df.drop("Fraud", axis=1)
y = df["Fraud"]

X_train, X_test, y_train, y_test = train_test_split(X, y, stratify=y, test_size=0.2, random_state=42)

# Modèle logistic regression
model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train)

# Calibration du modèle
calibrated_model = CalibratedClassifierCV(model, method='sigmoid', cv=5)
calibrated_model.fit(X_train, y_train)


joblib.dump(calibrated_model, "logreg_calibrated_model.pkl")
joblib.dump(le, "location_encoder.pkl")
