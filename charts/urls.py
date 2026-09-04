from django.urls import path

from charts import api, import_views

urlpatterns = [
    path("import/", import_views.picker, name="chart_import_picker"),
    path("import/review/", import_views.review, name="chart_import_review"),
    path("instruments/", api.instruments_with_charts, name="chart-instruments-list"),
    path("songs/conductor/", api.songs_for_conductor, name="chart-songs-conductor"),
    path("songs/<int:instrument_id>/", api.songs_for_instrument, name="chart-songs-for-instrument"),
    # Legacy endpoints (kept for backwards compatibility)
    path("songs/", api.songs_with_charts, name="chart-songs"),
    path("instruments/<int:song_id>/", api.instruments_for_song, name="chart-instruments"),
    path("parts/<int:song_id>/<int:instrument_id>/", api.charts_for_song_instrument, name="chart-parts"),
]
