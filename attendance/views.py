import logging
import os
import tempfile
from collections import OrderedDict
from datetime import date, datetime, timedelta
from io import StringIO

from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.core.management import call_command
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from attendance.forms import AttendanceReportFilterForm
from blowcomotion.models import AttendanceRecord, CachedGig, Instrument, Member, Section
from gigs.gigo import make_gigo_api_request

logger = logging.getLogger(__name__)

# Attendance Views


@login_required
@permission_required('blowcomotion.add_attendancerecord', raise_exception=True)
def attendance_capture(request, section_slug=None):
    """View for capturing attendance for a specific section"""
    sections = Section.objects.all().order_by('name')
    section = None
    is_no_section = False
    
    if section_slug:
        if section_slug == 'no-section':
            is_no_section = True
        else:
            section = get_object_or_404(Section, name__iexact=section_slug.replace('-', ' '))
    
    def build_member_entry(member, current_section):
        """Build template data and metadata for a member within the attendance form."""
        instruments = []
        seen_instrument_ids = set()

        if member.primary_instrument:
            instruments.append((member.primary_instrument, True))
            seen_instrument_ids.add(member.primary_instrument_id)

        for link in member.additional_instruments.all():
            instrument = link.instrument
            if instrument and instrument.id not in seen_instrument_ids:
                instruments.append((instrument, False))
                seen_instrument_ids.add(instrument.id)

        display_instrument = None
        if current_section:
            if member.primary_instrument and member.primary_instrument.section_id == current_section.id:
                display_instrument = member.primary_instrument
            else:
                for instrument, _ in instruments:
                    if instrument and instrument.section_id == current_section.id:
                        display_instrument = instrument
                        break
        elif instruments:
            display_instrument = instruments[0][0]

        if not display_instrument and instruments:
            display_instrument = instruments[0][0]

        entry = {
            'member': member,
            'display_instrument': display_instrument,
            'is_additional_for_section': bool(
                current_section and display_instrument and (
                    not member.primary_instrument or member.primary_instrument_id != display_instrument.id
                )
            ),
        }

        meta = {
            'section_instrument': display_instrument,
            'default': instruments[0][0] if instruments else None,
        }

        return entry, meta

    def resolve_played_instrument(member, meta):
        """Determine the instrument a member played based on metadata."""
        if meta:
            if meta.get('section_instrument'):
                return meta['section_instrument']
            if meta.get('default'):
                return meta['default']

        if member.primary_instrument:
            return member.primary_instrument

        for link in member.additional_instruments.all():
            if link.instrument:
                return link.instrument

        return None


    members_by_instrument = []
    member_entries_map = {}
    member_instrument_meta = {}
    section_member_ids = set()

    if is_no_section:
        section_members = Member.objects.filter(
            is_active=True,
            primary_instrument__isnull=True
        ).select_related('primary_instrument').prefetch_related('additional_instruments__instrument').order_by('first_name', 'last_name')

        for member in section_members:
            entry, meta = build_member_entry(member, None)
            member_entries_map[member.id] = entry
            member_instrument_meta[member.id] = meta
            section_member_ids.add(member.id)
    elif section:
        section_instruments = list(Instrument.objects.filter(section=section).order_by('name'))
        section_member_ids = set(section.get_members().values_list('id', flat=True))

        if section_member_ids:
            section_members = Member.objects.filter(
                id__in=section_member_ids
            ).select_related('primary_instrument').prefetch_related('additional_instruments__instrument').order_by('first_name', 'last_name')
        else:
            section_members = Member.objects.none()

        grouped_entries = OrderedDict(
            (instrument.id, {'instrument': instrument, 'entries': []})
            for instrument in section_instruments
        )

        for member in section_members:
            entry, meta = build_member_entry(member, section)

            # Skip members that do not align with this section in any way
            if section and not entry['display_instrument']:
                continue

            member_entries_map[member.id] = entry
            member_instrument_meta[member.id] = meta

            display_instrument = entry['display_instrument']
            if display_instrument and display_instrument.id in grouped_entries:
                grouped_entries[display_instrument.id]['entries'].append(entry)

        members_by_instrument = [
            group for group in grouped_entries.values()
            if group['entries']
        ]
    else:
        section_members = Member.objects.none()
    
    if request.method == 'POST':
        attendance_date_str = request.POST.get('attendance_date', date.today().strftime('%Y-%m-%d'))
        event_type_raw = request.POST.get('event_type', 'rehearsal')
        event_notes = request.POST.get('event_notes', '').strip()
        
        # Parse event_type: can be 'rehearsal', 'performance_no_gig', or 'gig_<id>'
        gig_id = None
        gig_title = None
        event_type = 'rehearsal'
        
        if event_type_raw.startswith('gig_'):
            # Extract gig ID from 'gig_<id>' format
            gig_id = event_type_raw.split('_', 1)[1]
            event_type = 'performance'
            # Get gig information from database cache
            try:
                cached_gig = CachedGig.get_gig_by_id(int(gig_id))
            except (TypeError, ValueError):
                cached_gig = None
            if cached_gig:
                gig_title = cached_gig.title
            else:
                # Fallback to API if not in cache (e.g., newly created gig)
                gig_data = make_gigo_api_request(f"/gigs/{gig_id}")
                if gig_data:
                    gig_title = gig_data.get('title', 'Unknown Gig')
        elif event_type_raw == 'performance_no_gig':
            event_type = 'performance'
        else:
            event_type = 'rehearsal'
        
        # Store form data in session for persistence
        request.session['attendance_form_data'] = {
            'attendance_date': attendance_date_str,
            'event_type': event_type_raw,  # Store the raw value for radio preselection
            'event_notes': event_notes
        }
        
        # Convert string to date object for consistent handling
        if isinstance(attendance_date_str, str):
            attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
        else:
            attendance_date = attendance_date_str
        
        # Create notes based on event type, gig, and custom notes
        if event_type == 'performance' and gig_title:
            event_notes_for_record = f"Performance: {gig_title}"
        elif event_type == 'performance' and event_notes:
            event_notes_for_record = f"Performance: {event_notes}"
        elif event_type == 'rehearsal' and event_notes:
            event_notes_for_record = f"Rehearsal: {event_notes}"
        elif event_notes:
            event_notes_for_record = event_notes
        else:
            event_notes_for_record = event_type.capitalize()
        
        success_count = 0
        errors = []
        
        # Process member attendance
        for member in section_members:
            checkbox_name = f'member_{member.id}'
            if checkbox_name in request.POST:
                try:
                    meta = member_instrument_meta.get(member.id)
                    played_instrument = resolve_played_instrument(member, meta)

                    # Create or update attendance record
                    attendance_record, created = AttendanceRecord.objects.get_or_create(
                        date=attendance_date,
                        member=member,
                        defaults={
                            'notes': event_notes_for_record,
                            'played_instrument': played_instrument,
                        }
                    )
                    if created:
                        success_count += 1
                    else:
                        fields_changed = []
                        # Update existing record to append event type in notes if not already present
                        if not attendance_record.notes:
                            attendance_record.notes = event_notes_for_record
                            fields_changed.append('notes')
                        else:
                            # Only append event_notes_for_record if it's not already present as a full entry
                            notes_entries = [entry.strip() for entry in attendance_record.notes.split(';') if entry.strip()]
                            if event_notes_for_record not in notes_entries:
                                notes_entries.append(event_notes_for_record)
                                attendance_record.notes = '; '.join(notes_entries)
                                fields_changed.append('notes')

                        current_instrument_id = attendance_record.played_instrument_id
                        new_instrument_id = played_instrument.id if played_instrument else None
                        if current_instrument_id != new_instrument_id:
                            attendance_record.played_instrument = played_instrument
                            fields_changed.append('played_instrument')

                        if fields_changed:
                            attendance_record.save(update_fields=list(set(fields_changed)))
                    
                    # Update member's last_seen field
                    member.last_seen = attendance_date
                    
                    # Update member's join_date if it hasn't been set yet and set is_active to True if it's False
                    fields_to_update = ['last_seen']
                    if not member.join_date:
                        member.join_date = attendance_date
                        fields_to_update.append('join_date')
                    if not member.is_active:
                        member.is_active = True
                        fields_to_update.append('is_active')
                    
                    member.save(update_fields=fields_to_update)
                except Exception as e:
                    errors.append(f"Error recording attendance for {member}: {str(e)}")
        
        # Also process any additional member IDs that might not be in section_members (e.g., inactive members)
        processed_member_ids = set(section_member_ids)
        for field_name, field_value in request.POST.items():
            if field_name.startswith('member_') and field_value == 'on':
                try:
                    member_id = int(field_name.split('_')[1])
                    if member_id not in processed_member_ids:
                        # This is a member not in section_members (probably inactive)
                        member = Member.objects.get(id=member_id)
                        meta = member_instrument_meta.get(member.id)
                        if not meta:
                            _, meta = build_member_entry(member, section if section else None)
                            member_instrument_meta[member.id] = meta
                            meta = member_instrument_meta[member.id]

                        played_instrument = resolve_played_instrument(member, meta)
                        
                        # Create or update attendance record
                        attendance_record, created = AttendanceRecord.objects.get_or_create(
                            date=attendance_date,
                            member=member,
                            defaults={
                                'notes': event_notes_for_record,
                                'played_instrument': played_instrument,
                            }
                        )
                        if created:
                            success_count += 1
                        else:
                            fields_changed = []
                            # Update existing record to append event type in notes if not already present
                            if not attendance_record.notes:
                                attendance_record.notes = event_notes_for_record
                                fields_changed.append('notes')
                            else:
                                # Only append event_notes_for_record if it's not already present as a full entry
                                notes_entries = [entry.strip() for entry in attendance_record.notes.split(';') if entry.strip()]
                                if event_notes_for_record not in notes_entries:
                                    notes_entries.append(event_notes_for_record)
                                    attendance_record.notes = '; '.join(notes_entries)
                                    fields_changed.append('notes')

                            current_instrument_id = attendance_record.played_instrument_id
                            new_instrument_id = played_instrument.id if played_instrument else None
                            if current_instrument_id != new_instrument_id:
                                attendance_record.played_instrument = played_instrument
                                fields_changed.append('played_instrument')

                            if fields_changed:
                                attendance_record.save(update_fields=list(set(fields_changed)))
                        
                        # Update member's last_seen field
                        member.last_seen = attendance_date
                        
                        # Update member's join_date if it hasn't been set yet and set is_active to True if it's False
                        fields_to_update = ['last_seen']
                        if not member.join_date:
                            member.join_date = attendance_date
                            fields_to_update.append('join_date')
                        if not member.is_active:
                            member.is_active = True
                            fields_to_update.append('is_active')
                        
                        member.save(update_fields=fields_to_update)
                except (ValueError, Member.DoesNotExist, Exception) as e:
                    errors.append(f"Error processing member ID {field_name}: {str(e)}")
        
        # Process guest attendance
        if section or is_no_section:
            # For no-section, use a special guest field name
            guest_field = f'guest_{section.id}' if section else 'guest_no_section'
            if guest_field in request.POST and request.POST[guest_field].strip():
                guest_names = [name.strip() for name in request.POST[guest_field].split('\n') if name.strip()]
                for guest_name in guest_names:
                    try:
                        guest_notes = f"Guest - {event_notes_for_record}"
                        AttendanceRecord.objects.get_or_create(
                            date=attendance_date,
                            guest_name=guest_name,
                            defaults={'notes': guest_notes}
                        )
                        success_count += 1
                    except Exception as e:
                        errors.append(f"Error recording guest attendance for {guest_name}: {str(e)}")
        
        # Return success message for HTMX requests
        # Get all records for this date to show in success message
        if section:
            # Get all records for this date and section
            todays_records = AttendanceRecord.objects.filter(
                date=attendance_date
            ).filter(
                Q(member__in=section_members) | Q(member__isnull=True)
            ).select_related('member', 'member__primary_instrument', 'played_instrument').order_by('member__first_name', 'member__last_name', 'guest_name')
        elif is_no_section:
            # Get all records for this date and no-section members
            todays_records = AttendanceRecord.objects.filter(
                date=attendance_date
            ).filter(
                Q(member__in=section_members) | Q(member__isnull=True)
            ).select_related('member', 'member__primary_instrument', 'played_instrument').order_by('member__first_name', 'member__last_name', 'guest_name')
        else:
            todays_records = AttendanceRecord.objects.filter(date=attendance_date).select_related('member', 'member__primary_instrument', 'played_instrument')
        
        context = {
            'success_count': success_count,
            'errors': errors,
            'attendance_date': attendance_date,
            'section': section,
            'is_no_section': is_no_section,
            'today': date.today(),
            'todays_records': todays_records
        }
        
        if request.headers.get('HX-Request'):
            return render(request, 'attendance/partials/capture_success.html', context)
        else:
            return render(request, 'attendance/capture_success.html', context)
    
    # Get persisted form values from session or query parameters
    form_data = request.session.get('attendance_form_data', {})
    
    # Check if date is being passed as a query parameter (for dynamic updates)
    query_date = request.GET.get('attendance_date')
    date_changed = False
    if query_date:
        date_changed = (form_data.get('attendance_date') != query_date)
        attendance_date = query_date
        # Update session with the new date
        form_data['attendance_date'] = attendance_date
        request.session['attendance_form_data'] = form_data
    else:
        attendance_date = form_data.get('attendance_date', date.today().strftime('%Y-%m-%d'))
    
    # event_type from session can be 'rehearsal', 'performance_no_gig', or 'gig_<id>'
    event_type_selection = form_data.get('event_type', None)
    event_notes = form_data.get('event_notes', '')
    
    # Get attendance records for the selected date to show checkmarks
    if isinstance(attendance_date, str):
        attendance_date_obj = datetime.strptime(attendance_date, '%Y-%m-%d').date()
    else:
        attendance_date_obj = attendance_date
    
    recorded_member_ids = set()
    if section_members:
        existing_records = AttendanceRecord.objects.filter(
            date=attendance_date_obj,
            member__in=section_members
        ).select_related('played_instrument')
        for record in existing_records:
            if record.member_id:
                recorded_member_ids.add(record.member_id)
                

    member_entries_sequence = []
    if section_members:
        for member in section_members:
            entry = member_entries_map.get(member.id)
            if entry:
                member_entries_sequence.append(entry)

    # Get gig choices for the current date using cached endpoint
    gig_choices = []
    date_str = None
    
    try:
        if isinstance(attendance_date, str):
            selected_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
            date_str = attendance_date
        else:
            selected_date = attendance_date
            date_str = attendance_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        logger.warning("Invalid attendance_date format: %s, error: %s", attendance_date, e)
        # Use today's date as fallback
        selected_date = date.today()
        date_str = selected_date.strftime('%Y-%m-%d')
        
    # Create cache key for this date
    cache_key = f"gigs_for_date_{date_str}"
    
    # Check cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        gig_choices = cached_result.get('gigs', [])
    else:
        # Fetch from database cache (synced from API via management command)
        cached_gigs = CachedGig.get_gigs_for_date(date_str)
        for gig in cached_gigs:
            gig_choices.append({
                'id': gig.gig_id,
                'title': gig.title,
                'date': gig.date.isoformat(),
            })
        
        # Cache the result for 10 minutes (fast lookup for repeated requests)
        result = {'gigs': gig_choices}
        cache.set(cache_key, result, 600)
    
    # Determine default event_type selection
    # Priority: last selected (if exists and not date changed) > first gig > rehearsal
    if not event_type_selection:
        # No selection in session, use default
        if gig_choices:
            # Select first gig by default
            event_type_selection = f"gig_{gig_choices[0]['id']}"
        else:
            # Select rehearsal by default
            event_type_selection = 'rehearsal'
    elif date_changed:
        # Date changed, but keep selection if it's still valid
        if event_type_selection.startswith('gig_'):
            # Check if the selected gig still exists for the new date
            selected_gig_id = event_type_selection.split('_', 1)[1]
            gig_exists = any(str(gig['id']) == selected_gig_id for gig in gig_choices)
            if not gig_exists:
                # Selected gig doesn't exist for new date, pick a new default
                if gig_choices:
                    event_type_selection = f"gig_{gig_choices[0]['id']}"
                else:
                    event_type_selection = 'rehearsal'
        elif event_type_selection == 'performance_no_gig':
            # If gigs now exist, switch to first gig
            if gig_choices:
                event_type_selection = f"gig_{gig_choices[0]['id']}"
        # If it's 'rehearsal', keep it as is
    
    context = {
        'section': section,
        'section_members': section_members,
        'members_by_instrument': members_by_instrument,
        'member_entries_map': member_entries_map,
        'member_entries_sequence': member_entries_sequence,
        'sections': sections,
        'is_no_section': is_no_section,
        'today': date.today(),
        'attendance_date': attendance_date,
        'event_type_selection': event_type_selection,
        'event_notes': event_notes,
        'gig_choices': gig_choices,
        'recorded_member_ids': recorded_member_ids,
    }
    
    # For HTMX section switching, return the main content including navigation
    if request.headers.get('HX-Request'):
        # Check if this is a date change request (has attendance_date parameter)
        if query_date and (section or is_no_section):
            # For date changes when a section is selected, return just the members section to update checkmarks
            return render(request, 'attendance/partials/members_section.html', context)
        else:
            # For section navigation or when no section is selected, return the full capture content
            return render(request, 'attendance/partials/capture_content.html', context)
    
    return render(request, 'attendance/capture.html', context)


@login_required
@permission_required('blowcomotion.add_attendancerecord', raise_exception=True)
@require_http_methods(["GET", "POST"])
def inactive_members(request):
    """View for managing inactive members - display list with reactivation buttons"""
    
    # Get all inactive members
    inactive_members_list = Member.objects.filter(is_active=False).order_by('first_name', 'last_name')
    
    # Handle POST requests for member reactivation
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        if member_id:
            try:
                member = Member.objects.get(id=member_id, is_active=False)
                member.is_active = True
                member.save(update_fields=['is_active'])
                
                # Return success message for HTMX requests
                success_message = f'Successfully reactivated {member.first_name} {member.last_name}'
                
                context = {
                    'message': success_message,
                    'reactivated_member': member,
                    'sections': Section.objects.all().order_by('name')  # Add sections for navigation
                }
                
                if request.headers.get('HX-Request'):
                    # Refresh the inactive members list after reactivation
                    inactive_members_list = Member.objects.filter(is_active=False).order_by('first_name', 'last_name')
                    context['inactive_members'] = inactive_members_list
                    return render(request, 'attendance/partials/inactive_members_content.html', context)
                else:
                    context['inactive_members'] = inactive_members_list
                    return render(request, 'attendance/inactive_members.html', context)
                    
            except Member.DoesNotExist:
                context = {
                    'error': 'Member not found or already active',
                    'inactive_members': inactive_members_list,
                    'sections': Section.objects.all().order_by('name')  # Add sections for navigation
                }
                
                if request.headers.get('HX-Request'):
                    return render(request, 'attendance/partials/inactive_members_content.html', context)
                else:
                    return render(request, 'attendance/inactive_members.html', context)
            except Exception as e:
                context = {
                    'error': f'Error reactivating member: {str(e)}',
                    'inactive_members': inactive_members_list,
                    'sections': Section.objects.all().order_by('name')  # Add sections for navigation
                }
                
                if request.headers.get('HX-Request'):
                    return render(request, 'attendance/partials/inactive_members_content.html', context)
                else:
                    return render(request, 'attendance/inactive_members.html', context)
    
    # GET request - display inactive members list
    context = {
        'inactive_members': inactive_members_list,
        'sections': Section.objects.all().order_by('name')  # For navigation
    }
    
    # For HTMX requests, return just the content
    if request.headers.get('HX-Request'):
        return render(request, 'attendance/partials/inactive_members_content.html', context)
    
    return render(request, 'attendance/inactive_members.html', context)


@login_required
@permission_required('blowcomotion.view_attendancerecord', raise_exception=True)
def attendance_reports(request):
    """View for attendance reports - overall summary"""
    filter_form = AttendanceReportFilterForm(request.GET or None)
    
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    section_id = request.GET.get('section')
    member_id = request.GET.get('member')
    
    # Build query
    attendance_records = AttendanceRecord.objects.all()
    
    if start_date:
        attendance_records = attendance_records.filter(date__gte=start_date)
    if end_date:
        attendance_records = attendance_records.filter(date__lte=end_date)
    
    if member_id:
        attendance_records = attendance_records.filter(member_id=member_id)
    
    if section_id:
        section = Section.objects.get(id=section_id)
        # Include members whose primary or additional instruments belong to this section
        section_member_ids = section.get_members().values_list('id', flat=True)
        attendance_records = attendance_records.filter(
            Q(member_id__in=section_member_ids) | Q(member__isnull=True)
        )
    
    # Get summary statistics
    total_records = attendance_records.count()
    member_records = attendance_records.filter(member__isnull=False).count()
    guest_records = attendance_records.filter(guest_name__isnull=False).count()
    
    # Group by date
    attendance_by_date = attendance_records.values('date').annotate(
        member_count=Count('member', filter=Q(member__isnull=False)),
        guest_count=Count('guest_name', filter=Q(guest_name__isnull=False)),
        total_count=Count('id')
    ).order_by('-date')
    
    # Get sections for navigation
    sections = Section.objects.all().order_by('name')
    
    context = {
        'filter_form': filter_form,
        'attendance_records': attendance_records.select_related('member', 'member__primary_instrument', 'played_instrument').order_by('-date', 'member__first_name', 'member__last_name')[:100],  # Limit for performance
        'attendance_by_date': attendance_by_date,
        'total_records': total_records,
        'member_records': member_records,
        'guest_records': guest_records,
        'sections': sections
    }
    
    # For HTMX filter requests, return just the filtered content
    if request.headers.get('HX-Request'):
        # Check if this is a filter request vs navigation request
        if any(param in request.GET for param in ['start_date', 'end_date', 'section', 'member']):
            return render(request, 'attendance/partials/reports_content.html', context)
        else:
            return render(request, 'attendance/partials/all_reports_content.html', context)
    
    return render(request, 'attendance/reports.html', context)

@login_required
@permission_required('blowcomotion.view_attendancerecord', raise_exception=True)
def attendance_section_report_new(request, section_slug):
    """View for attendance reports for a specific section"""
    section = get_object_or_404(Section, name__iexact=section_slug.replace('-', ' '))
    
    # Get date range (default to last 12 weeks)
    end_date = date.today()
    start_date = end_date - timedelta(weeks=12)
    
    if request.GET.get('start_date'):
        start_date = date.fromisoformat(request.GET.get('start_date'))
    if request.GET.get('end_date'):
        end_date = date.fromisoformat(request.GET.get('end_date'))
    
    # Include members whose primary or additional instruments belong to this section
    section_members = section.get_members().select_related(
        'primary_instrument'
    ).prefetch_related('additional_instruments__instrument').order_by('first_name', 'last_name')
    
    section_member_ids = list(section_members.values_list('id', flat=True))
    
    # Get attendance records for this section (filter by members in this section)
    attendance_records = AttendanceRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).filter(
        Q(member_id__in=section_member_ids) | Q(member__isnull=True)
    ).order_by('-date')
    
    # Calculate member attendance percentages
    member_attendance = {}
    for member in section_members:
        member_records = attendance_records.filter(member=member)
        
        # Calculate Tuesdays in the period for this member
        member_tuesdays = 0
        current_date = max(start_date, member.join_date) if member.join_date else start_date
        while current_date <= end_date:
            if current_date.weekday() == 1:  # Tuesday
                member_tuesdays += 1
            current_date += timedelta(days=1)
        
        attendance_percentage = (member_records.count() / member_tuesdays * 100) if member_tuesdays > 0 else 0
        member_attendance[member] = {
            'count': member_records.count(),
            'total_tuesdays': member_tuesdays,
            'percentage': round(attendance_percentage, 1)
        }
    
    # Group attendance by date
    attendance_by_date = attendance_records.values('date').annotate(
        member_count=Count('member', filter=Q(member__isnull=False)),
        guest_count=Count('guest_name', filter=Q(guest_name__isnull=False)),
        total_count=Count('id')
    ).order_by('-date')
    
    context = {
        'section': section,
        'section_members': section_members,
        'attendance_records': attendance_records.select_related('member', 'member__primary_instrument', 'played_instrument'),
        'member_attendance': member_attendance,
        'attendance_by_date': attendance_by_date,
        'start_date': start_date,
        'end_date': end_date
    }
    
    # For HTMX requests, return just the content
    if request.headers.get('HX-Request'):
        return render(request, 'attendance/partials/section_report_content.html', context)
    
    return render(request, 'attendance/section_report.html', context)


def export_attendance_csv(request):
    if not request.user.has_perm('blowcomotion.access_real_data_exports'):
        logger.warning("Unauthorized access attempt to export attendance by user %s", request.user.username)
        return JsonResponse({'error': 'You do not have permission to access this feature'}, status=403)

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    temp_path = temp_file.name
    temp_file.close()

    try:
        logger.info(
            "Starting attendance export by user %s (start_date=%s, end_date=%s)",
            request.user.username,
            start_date or 'min',
            end_date or 'max',
        )
        command_kwargs = {
            'output': temp_path,
            'stdout': StringIO(),
        }
        if start_date:
            command_kwargs['start_date'] = start_date
        if end_date:
            command_kwargs['end_date'] = end_date

        call_command('export_attendance_to_csv', **command_kwargs)

    except Exception as e:
        logger.error("Error during attendance export by user %s: %s", request.user.username, str(e))
        return JsonResponse({'error': str(e)}, status=500)
    else:
        with open(temp_path, 'rb') as csv_file:
            csv_data = csv_file.read()

        timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        filename = f'attendance_export_{timestamp}.csv'
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        logger.info("Attendance export completed successfully by user %s", request.user.username)
        return response
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning("Temporary file %s could not be removed after attendance export", temp_path)

