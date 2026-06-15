from .models import User, Engine, Sensor_Leaky_Data, Engine_Test
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

class EngineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Engine
        fields = "__all__"

class SensorLeakyDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sensor_Leaky_Data
        fields = "__all__"

class EngineTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Engine_Test
        fields = "__all__"