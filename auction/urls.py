from django.urls import path

from auction import sms, views

urlpatterns = [
    path("<int:auction_id>/item/<int:number>/", views.item_detail, name="auction-item-detail"),
    path("<int:auction_id>/item/<int:number>/bid/", views.place_bid_view, name="auction-place-bid"),
    path("<int:auction_id>/grid/", views.grid_partial, name="auction-grid"),
    path("sms/", sms.sms_webhook, name="auction-sms-webhook"),
]
