from django.urls import path

from auction import views

urlpatterns = [
    path("<int:auction_id>/item/<int:number>/", views.item_detail, name="auction-item-detail"),
    path("<int:auction_id>/item/<int:number>/bid/", views.place_bid_view, name="auction-place-bid"),
]
