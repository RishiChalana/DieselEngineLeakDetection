from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserSerializer
from  rest_framework.authtoken.models import Token
from rest_framework import status
from rest_framework.authentication import authenticate
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
# Create your views here.


class Signup(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {'token': token.key, 'user': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )
    
class Login(APIView):
    def post(self,request,*args,**kwargs):
        data=request.data.copy()
        user=authenticate(
            username=data["username"],
            password=data["password"],
        )
        if not user:
            return Response({'error':'User not found'},status=status.HTTP_401_UNAUTHORIZED)
        token,_=Token.objects.get_or_create(user=user)
        user.save()
        return Response({'token':token.key,'user':UserSerializer(user).data},status=status.HTTP_200_OK)
    
class Logout(APIView):
    authentication_classes=[TokenAuthentication]
    permission_classes=[IsAuthenticated]
    def post(self ,request,*args,**kwargs):
        request.auth.delete()
        return Response({'message':"Logged out Successfully"},status=status.HTTP_200_OK)
    
class Delete_Account(APIView):
    def delete(self,request,*args,**kwargs):
        user=request.user
        request.auth.delete()
        user.delete()
        return Response({'message':"User successfully deleted"},status=status.HTTP_200_OK)
        
        


