import numpy as np


class KalmanFilter2D:

    def __init__(self, dt=1.0, process_variance=1e-3, measurement_variance=1e-2):

        self.dt = dt

        self.x = np.zeros((2, 1))

        self.P = np.eye(2)

        self.A = np.array([
            [1, dt],
            [0, 1]
        ])

        self.H = np.array([[1, 0]])

        self.Q = process_variance * np.eye(2)

        self.R = np.array([[measurement_variance]])

        self.initialized = False

    def update(self, measurement):

        z_k = np.array([[measurement]])  

        if not self.initialized:
            self.x[0, 0] = measurement
            self.initialized = True
            return measurement

        x_pred = self.A @ self.x
        P_pred = self.A @ self.P @ self.A.T + self.Q

        y_k = z_k - self.H @ x_pred

        S_k = self.H @ P_pred @ self.H.T + self.R

        K_k = P_pred @ self.H.T @ np.linalg.inv(S_k)

        self.x = x_pred + K_k @ y_k
        self.P = (np.eye(2) - K_k @ self.H) @ P_pred

        return float(self.x[0, 0])
