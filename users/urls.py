from django.urls import path
from rest_framework.routers import DefaultRouter

from users.views import RegisterView, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = router.urls

urlpatterns += [
    path("register/", RegisterView.as_view(), name="register"),
]
