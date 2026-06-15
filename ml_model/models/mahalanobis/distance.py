import numpy as np
import joblib
from pathlib import Path


class MahalanobisDistance:

    def __init__(self):
        base_dir = Path(__file__).resolve().parents[2]  # ml_model
        model_path = base_dir / "models" / "mahalanobis" / "encoded" /"mahal_model.pkl"

        bundle = joblib.load(model_path)

        self.mean = bundle["mean"]
        self.inv_cov = bundle["inv_cov"]
        self.scalar = bundle["scaler"]
        self.k = bundle["k"]

    def calculate_mahalanobis_distance(self,x):
        x=self.scalar.transform(x.reshape(1,-1)).flatten()
        x_mu=(x-self.mean)
        d2=(x_mu).T@self.inv_cov@(x_mu)
        return float(d2)     

    def calculate_z_score(self,x):
        d2=self.calculate_mahalanobis_distance(x)
        z_score=(d2-self.k)/np.sqrt(2*self.k)
        return float(z_score)
    
