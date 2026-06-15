from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import datetime

# Create your models here.

ROLE_CHOICES = (
    ('viewer', 'Viewer'),
    ('tester', 'Tester'),
    ('admin', 'Admin'),
)

TEST_CHOICES = (
    ('Pass', 'Pass'),
    ('Fail', 'Fail'),
)
ENGINE_TYPE_CHOICES = (
    ('diesel', 'Diesel'),
    ('petrol', 'Petrol'),
)
class User(AbstractUser):
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='viewer')
    history = models.JSONField(default=dict)
    last_login_time = models.DateTimeField(default=datetime.now)
    def __str__(self):
        return self.username

class Engine(models.Model):
    EID = models.AutoField(primary_key=True)
    model_no = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=20, choices=ENGINE_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    photo = models.ImageField(upload_to='engine_photos/', null=True, blank=True)
    def __str__(self):
        return self.model_no

class Sensor_Leaky_Data(models.Model):
    SID = models.AutoField(primary_key=True)
    rolling_window_data = models.JSONField(default=dict)
    next_steps = models.TextField()
    def __str__(self):
        return str(self.SID)

class Engine_Test(models.Model):
    engine = models.ForeignKey(Engine, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sensor = models.ForeignKey(Sensor_Leaky_Data, on_delete=models.CASCADE)
    test_check = models.CharField(max_length=10, choices=TEST_CHOICES)
    checked_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Test {self.id} - {self.test_check}"
