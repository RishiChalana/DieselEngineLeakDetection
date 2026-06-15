from ml_model.kalman.kalman_filter import KalmanFilter2D


class KalmanLayer:

    def __init__(self):

        self.filters = {

            "rpm": KalmanFilter2D(
                process_variance=516071.408893 * 0.01,
                measurement_variance=172046.072276 * 0.05
            ),

            "MAF": KalmanFilter2D(
                process_variance=149069.903842 * 0.01,
                measurement_variance=49584.498558 * 0.05
            ),

            "boost_pressure": KalmanFilter2D(
                process_variance=0.168738 * 0.01,
                measurement_variance=0.056331 * 0.05
            ),

            "exhaust_pressure": KalmanFilter2D(
                process_variance=0.543919 * 0.01,
                measurement_variance=0.180762 * 0.05
            ),

            "MAP": KalmanFilter2D(
                process_variance=0.178735 * 0.01,
                measurement_variance=0.059702 * 0.05
            ),

            "fuel_rate": KalmanFilter2D(
                process_variance=1313.174310 * 0.01,
                measurement_variance=437.976408 * 0.05
            ),

            "EGT": KalmanFilter2D(
                process_variance=12344.146522 * 0.01,
                measurement_variance=4117.523997 * 0.05
            ),

            "VGT": KalmanFilter2D(
                process_variance=122.878105 * 0.01,
                measurement_variance=40.973824 * 0.05
            ),

            "DPF_delta": KalmanFilter2D(
                process_variance=283436300.696780 * 0.01,
                measurement_variance=94082387.843457 * 0.05
            ),

            "turbo_speed": KalmanFilter2D(
                process_variance=233781182.182724 * 0.01,
                measurement_variance=77918534.394252 * 0.05
            ),
            "ambient_pressure": KalmanFilter2D(
                process_variance=0.011176 * 0.01,
                measurement_variance=0.003723 * 0.05
            ),
            "IAT": KalmanFilter2D(
                process_variance=788.921115 * 0.01,
                measurement_variance=262.863229 * 0.05
            ),
        }

    def filter(self, data_dict):

        filtered_data = {}

        for key, value in data_dict.items():

            if key in self.filters:
                filtered_data[key] = self.filters[key].update(value)
            else:
                filtered_data[key] = value

        return filtered_data
