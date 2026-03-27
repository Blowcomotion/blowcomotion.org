"""
Chart Library API endpoints for the ChartLibraryBlock.

Provides JSON endpoints for:
- Listing songs that have charts (with optional search)
- Listing instruments for a given song that have charts
- Listing chart parts for a song+instrument combination
"""

from django.db.models import Exists, OuterRef
from django.http import JsonResponse

from blowcomotion.models import Chart, Instrument, Song


def instruments_with_charts(request):
    """
    GET /charts/instruments/
    
    Returns all instruments that have at least one chart with a PDF uploaded,
    grouped by section. This is the entry point for the instrument-first flow.
    """
    # Get distinct instrument IDs that have charts with PDFs
    instrument_ids = Chart.objects.filter(
        pdf__isnull=False
    ).values_list('instrument_id', flat=True).distinct()
    
    instruments = Instrument.objects.filter(
        pk__in=instrument_ids
    ).select_related('section').order_by('section__name', 'name')
    
    # Group by section
    sections_data = {}
    for instrument in instruments:
        section_name = instrument.section.name if instrument.section else 'Other'
        section_id = instrument.section.id if instrument.section else 0
        
        if section_id not in sections_data:
            sections_data[section_id] = {
                'id': section_id,
                'name': section_name,
                'instruments': []
            }
        
        sections_data[section_id]['instruments'].append({
            'id': instrument.id,
            'name': instrument.name,
        })
    
    # Convert to list sorted by section name
    sections_list = sorted(sections_data.values(), key=lambda x: x['name'])
    
    return JsonResponse({'sections': sections_list})


def songs_for_instrument(request, instrument_id):
    """
    GET /charts/songs/<instrument_id>/
    GET /charts/songs/<instrument_id>/?search=<query>
    
    Returns songs that have charts for the given instrument.
    Each song includes its chart parts inline to avoid an extra API call.
    """
    try:
        instrument = Instrument.objects.get(pk=instrument_id)
    except Instrument.DoesNotExist:
        return JsonResponse({'error': 'Instrument not found'}, status=404)
    
    search_query = request.GET.get('search', '').strip()
    
    # Get songs that have charts for this instrument
    song_ids = Chart.objects.filter(
        instrument=instrument,
        pdf__isnull=False
    ).values_list('song_id', flat=True).distinct()
    
    songs = Song.objects.filter(
        pk__in=song_ids,
        active=True
    ).select_related(
        'recording'
    ).prefetch_related(
        'videos'
    ).order_by('title')
    
    if search_query:
        songs = songs.filter(title__icontains=search_query)
    
    data = []
    for song in songs:
        # Collect videos
        videos = []
        for video in song.videos.all():
            videos.append({'url': video.url, 'title': video.title})
        
        # Get charts for this song+instrument combination
        charts = Chart.objects.filter(
            song=song,
            instrument=instrument,
            pdf__isnull=False
        ).select_related('pdf').order_by('part')
        
        charts_data = []
        for chart in charts:
            part_name = chart.part if chart.part else instrument.name
            charts_data.append({
                'id': chart.id,
                'part': part_name,
                'pdf_url': chart.pdf.url if chart.pdf else None,
                'pdf_title': chart.pdf.title if chart.pdf else None,
            })
        
        song_data = {
            'id': song.id,
            'title': song.title,
            'has_recording': bool(song.recording and song.recording.file),
            'has_video': len(videos) > 0,
            'videos': videos,
            'charts': charts_data,
        }
        if song.recording and song.recording.file:
            song_data['recording_url'] = song.recording.file.url
        data.append(song_data)
    
    return JsonResponse({
        'instrument_id': instrument.id,
        'instrument_name': instrument.name,
        'songs': data
    })


def songs_with_charts(request):
    """
    GET /charts/songs/
    GET /charts/songs/?search=<query>
    
    Returns songs that have at least one chart with a PDF uploaded.
    Filters out songs without any charts to avoid dead-ends.
    """
    search_query = request.GET.get('search', '').strip()
    
    # Subquery to check if song has at least one chart with a PDF
    has_chart_with_pdf = Chart.objects.filter(
        song=OuterRef('pk'),
        pdf__isnull=False
    )
    
    songs = Song.objects.filter(
        active=True
    ).select_related(
        'recording'
    ).prefetch_related(
        'videos'
    ).annotate(
        has_charts=Exists(has_chart_with_pdf)
    ).filter(
        has_charts=True
    ).order_by('title')
    
    if search_query:
        songs = songs.filter(title__icontains=search_query)
    
    data = []
    for song in songs:
        # Collect videos relation
        videos = []
        for video in song.videos.all():
            videos.append({'url': video.url, 'title': video.title})
        
        song_data = {
            'id': song.id,
            'title': song.title,
            'has_recording': bool(song.recording and song.recording.file),
            'has_video': len(videos) > 0,
            'videos': videos,
        }
        if song.recording and song.recording.file:
            song_data['recording_url'] = song.recording.file.url
        data.append(song_data)
    
    return JsonResponse({'songs': data})


def instruments_for_song(request, song_id):
    """
    GET /charts/instruments/<song_id>/
    
    Returns instruments that have charts for the given song, grouped by section.
    Only includes instruments that have at least one chart with a PDF.
    """
    try:
        song = Song.objects.get(pk=song_id, active=True)
    except Song.DoesNotExist:
        return JsonResponse({'error': 'Song not found'}, status=404)
    
    # Get instruments that have charts with PDFs for this song
    instrument_ids = Chart.objects.filter(
        song=song,
        pdf__isnull=False
    ).values_list('instrument_id', flat=True).distinct()
    
    instruments = Instrument.objects.filter(
        pk__in=instrument_ids
    ).select_related('section').order_by('section__name', 'name')
    
    # Group by section and include chart data
    sections_data = {}
    for instrument in instruments:
        section_name = instrument.section.name if instrument.section else 'Other'
        section_id = instrument.section.id if instrument.section else 0
        
        if section_id not in sections_data:
            sections_data[section_id] = {
                'id': section_id,
                'name': section_name,
                'instruments': []
            }
        
        # Get charts for this instrument and song
        charts = Chart.objects.filter(
            song=song,
            instrument=instrument,
            pdf__isnull=False
        ).select_related('pdf').order_by('part')
        
        charts_data = []
        for chart in charts:
            part_name = chart.part if chart.part else instrument.name
            charts_data.append({
                'id': chart.id,
                'part': part_name,
                'pdf_url': chart.pdf.url if chart.pdf else None,
                'pdf_title': chart.pdf.title if chart.pdf else None,
            })
        
        sections_data[section_id]['instruments'].append({
            'id': instrument.id,
            'name': instrument.name,
            'charts': charts_data,
        })
    
    # Convert to list sorted by section name
    sections_list = sorted(sections_data.values(), key=lambda x: x['name'])
    
    return JsonResponse({
        'song_id': song.id,
        'song_title': song.title,
        'sections': sections_list
    })


def charts_for_song_instrument(request, song_id, instrument_id):
    """
    GET /charts/parts/<song_id>/<instrument_id>/
    
    Returns chart parts for the given song and instrument combination.
    Each chart includes a link to the PDF document.
    """
    try:
        song = Song.objects.get(pk=song_id, active=True)
    except Song.DoesNotExist:
        return JsonResponse({'error': 'Song not found'}, status=404)
    
    try:
        instrument = Instrument.objects.get(pk=instrument_id)
    except Instrument.DoesNotExist:
        return JsonResponse({'error': 'Instrument not found'}, status=404)
    
    charts = Chart.objects.filter(
        song=song,
        instrument=instrument,
        pdf__isnull=False
    ).select_related('pdf').order_by('part')
    
    charts_data = []
    for chart in charts:
        part_name = chart.part if chart.part else instrument.name
        charts_data.append({
            'id': chart.id,
            'part': part_name,
            'pdf_url': chart.pdf.url if chart.pdf else None,
            'pdf_title': chart.pdf.title if chart.pdf else None,
        })
    
    return JsonResponse({
        'song_id': song.id,
        'song_title': song.title,
        'instrument_id': instrument.id,
        'instrument_name': instrument.name,
        'charts': charts_data
    })
