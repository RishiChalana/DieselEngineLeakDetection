from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services.pipeline import process_engine_data

class Predict(APIView):
    def post(self,request,*args,**kwargs):
        leaky_sample = {
           "rpm":1714.9389039077766,
           "fuel_rate":92.6468374088145,
           "turbo_speed":62902.971489603835,
           "boost_pressure":1.510927663914437,
           "MAP":2.4943241697461995,
           "IAT":306.0065332267955,
           "MAF":1000.0,
           "EGT":819.4384934476335,
           "exhaust_pressure":3.5,
           "VGT":41.78000173882777,
           "DPF_delta":50203.11159055024,
           "ambient_pressure":0.9948599597619494
        }

    
        z_score=process_engine_data(leaky_sample)
        return Response(z_score,status=status.HTTP_200_OK)
