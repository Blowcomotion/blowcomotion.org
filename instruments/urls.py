from django.urls import path

from instruments import views

urlpatterns = [
    path("staying/", views.instrument_rental_staying, name="instrument-rental-staying"),
    path("patreon-updated/", views.instrument_rental_patreon_updated, name="instrument-rental-patreon-updated"),
    path("return/", views.instrument_rental_return, name="instrument-rental-return"),
]
