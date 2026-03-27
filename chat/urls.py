from django.urls import path

from .views import chat_home

app_name = "chat"

urlpatterns = [
    path("", chat_home, name="home"),
]
