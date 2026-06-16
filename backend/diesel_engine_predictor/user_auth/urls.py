from django.urls import path
from .views import Login, Logout, Delete_Account, Signup, Health

urlpatterns = [
    path('login/', Login.as_view(), name="login"),
    path('signup/', Signup.as_view(), name="signup"),
    path('logout/', Logout.as_view(), name="logout"),
    path('delete_account/', Delete_Account.as_view(), name="delete_account"),
    path('health/', Health.as_view(), name="health"),
]
