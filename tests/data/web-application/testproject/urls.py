from typing import Any

from django.contrib import admin  # pylint: disable=import-error
from django.urls import path  # pylint: disable=import-error
from django.http import HttpResponse  # pylint: disable=import-error


def hello_world(request: Any) -> HttpResponse:  # pylint: disable=unused-argument
    return HttpResponse("Hello, Django in Docker!")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", hello_world, name="hello"),
]
