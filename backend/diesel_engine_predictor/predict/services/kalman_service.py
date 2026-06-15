from ml_model.kalman.kalman_layer import KalmanLayer


KALMAN_LAYER=KalmanLayer()

def apply_kalman(sensor_data:dict):
    return KALMAN_LAYER.filter(sensor_data)


