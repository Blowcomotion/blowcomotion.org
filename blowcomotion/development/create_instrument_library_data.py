#!/usr/bin/env python
import os
import sys
from datetime import datetime, timedelta

import django

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blowcomotion.settings.dev')
django.setup()

from blowcomotion.models import (
    Instrument,
    InstrumentHistoryLog,
    LibraryInstrument,
    Member,
    Section,
)


def create_instrument_library_data():
    """
    Create a marching brass band instrument library with:
    trumpet, french horn, trombone, baritone, tuba, flute, clarinet, 
    alto saxophone, tenor saxophone, baritone saxophone, 
    snare drum, bass drum, cymbals, quads, bells
    """
    
    # Create or get sections
    high_brass, _ = Section.objects.get_or_create(name="High Brass")
    low_brass, _ = Section.objects.get_or_create(name="Low Brass")
    woodwinds, _ = Section.objects.get_or_create(name="Woodwinds")
    percussion, _ = Section.objects.get_or_create(name="Percussion")
    
    # Create or get instruments with their sections
    instruments_data = [
        # High Brass
        ("Trumpet", high_brass, [
            ("TR-001", "Yamaha YTR-200AD"),
            ("TR-002", "Bach TR300H2"),
            ("TR-003", "Jupiter JTR700"),
        ]),
        ("French Horn", high_brass, [
            ("FH-001", "Holton H179"),
            ("FH-002", "Jupiter JHR1100"),
        ]),
        
        # Low Brass
        ("Trombone", low_brass, [
            ("TB-001", "Bach TB200"),
            ("TB-002", "Yamaha YSL-354"),
            ("TB-003", "Jupiter JTB700"),
        ]),
        ("Baritone", low_brass, [
            ("BR-001", "King 627"),
            ("BR-002", "Yamaha YEP-321"),
        ]),
        ("Tuba", low_brass, [
            ("TU-001", "Yamaha YBB-201"),
            ("TU-002", "Jupiter JTU1010"),
        ]),
        
        # Woodwinds
        ("Flute", woodwinds, [
            ("FL-001", "Yamaha YFL-222"),
            ("FL-002", "Gemeinhardt 2SP"),
            ("FL-003", "Jupiter JFL700"),
        ]),
        ("Clarinet", woodwinds, [
            ("CL-001", "Buffet B12"),
            ("CL-002", "Yamaha YCL-255"),
            ("CL-003", "Jupiter JCL700N"),
        ]),
        ("Alto Saxophone", woodwinds, [
            ("AS-001", "Yamaha YAS-280"),
            ("AS-002", "Jupiter JAS700"),
        ]),
        ("Tenor Saxophone", woodwinds, [
            ("TS-001", "Yamaha YTS-280"),
            ("TS-002", "Jupiter JTS700"),
        ]),
        ("Baritone Saxophone", woodwinds, [
            ("BS-001", "Yamaha YBS-52"),
        ]),
        
        # Percussion
        ("Snare Drum", percussion, [
            ("SD-001", "Pearl Free Floating 14x5.5"),
            ("SD-002", "Ludwig LM402"),
        ]),
        ("Bass Drum", percussion, [
            ("BD-001", "Pearl Championship 28x14"),
            ("BD-002", "Yamaha MB-8300 Series"),
        ]),
        ("Cymbals", percussion, [
            ("CY-001", "Zildjian 18-inch Crash"),
            ("CY-002", "Sabian AA 20-inch Ride"),
        ]),
        ("Quads", percussion, [
            ("QD-001", "Pearl Championship Quads 10/12/13/14"),
        ]),
        ("Bells", percussion, [
            ("BL-001", "Yamaha 2.5 Octave Glockenspiel"),
        ]),
    ]
    
    created_count = 0
    
    for instrument_name, section, inventory_items in instruments_data:
        # Get or create the instrument type
        instrument, _ = Instrument.objects.get_or_create(
            name=instrument_name,
            defaults={"section": section}
        )
        
        # Create library instruments (physical inventory)
        for serial_number, description in inventory_items:
            library_instrument, created = LibraryInstrument.objects.get_or_create(
                instrument=instrument,
                serial_number=serial_number,
                defaults={
                    "status": LibraryInstrument.STATUS_AVAILABLE,
                    "comments": description,
                }
            )
            if created:
                created_count += 1
                print(f"Created: {instrument_name} - {serial_number} ({description})")
            else:
                print(f"Already exists: {instrument_name} - {serial_number}")
    
    print(f"\nTotal library instruments created: {created_count}")
    return created_count


def create_rental_history_logs():
    """
    Create realistic rental and maintenance history logs for development.
    Includes: acquisitions, rentals, returns, repairs, and location checks.
    """
    # Get some members for rentals (or skip if none exist)
    members = list(Member.objects.filter(is_active=True)[:5])
    if not members:
        print("\nNo active members found. Skipping rental assignments.")
        print("Run: python blowcomotion/development/create_test_members.py")
        members = []
    
    # Get all library instruments
    all_instruments = list(LibraryInstrument.objects.all())
    if not all_instruments:
        print("\nNo library instruments found. Run create_instrument_library_data() first.")
        return 0
    
    logs_created = 0
    today = datetime.now().date()
    
    # 1. Add acquisition logs for all instruments (when they were added to inventory)
    print("\n--- Creating Acquisition Logs ---")
    for instrument in all_instruments[:10]:  # First 10 instruments
        acquisition_date = today - timedelta(days=365 * 2)  # Acquired 2 years ago
        log, created = InstrumentHistoryLog.objects.get_or_create(
            library_instrument=instrument,
            event_category=InstrumentHistoryLog.EVENT_ACQUISITION,
            event_date=acquisition_date,
            defaults={
                'notes': f'Acquired {instrument.instrument.name} - {instrument.comments or "No details"}'
            }
        )
        if created:
            logs_created += 1
            print(f"  ✓ Acquisition: {instrument.instrument.name} {instrument.serial_number}")
    
    # 2. Create some rental scenarios with history
    if members:
        print("\n--- Creating Rental Scenarios ---")
        rental_instruments = all_instruments[:min(len(members), 5)]
        
        for idx, (instrument, member) in enumerate(zip(rental_instruments, members)):
            # Set up the rental
            rental_date = today - timedelta(days=90 + (idx * 30))  # Stagger rentals
            agreement_date = rental_date - timedelta(days=7)
            
            instrument.status = LibraryInstrument.STATUS_RENTED
            instrument.member = member
            instrument.rental_date = rental_date
            instrument.agreement_signed_date = agreement_date
            instrument.review_date_6_month = rental_date + timedelta(days=180)
            instrument.review_date_12_month = rental_date + timedelta(days=365)
            instrument.patreon_active = idx % 2 == 0  # Alternate Patreon status
            if instrument.patreon_active:
                instrument.patreon_amount = 5.00 + (idx * 2.50)
            instrument.save()
            
            # Create rental log
            log, created = InstrumentHistoryLog.objects.get_or_create(
                library_instrument=instrument,
                event_category=InstrumentHistoryLog.EVENT_OUT_FOR_LOAN,
                event_date=rental_date,
                defaults={
                    'notes': f'Rented to {member.first_name} {member.last_name}. Agreement signed {agreement_date}.'
                }
            )
            if created:
                logs_created += 1
                print(f"  ✓ Rental: {instrument.instrument.name} {instrument.serial_number} → {member.first_name} {member.last_name}")
    
    # 3. Add some repair history
    print("\n--- Creating Repair History ---")
    repair_instruments = all_instruments[10:13] if len(all_instruments) > 10 else []
    
    for instrument in repair_instruments:
        # Out for repair
        repair_out_date = today - timedelta(days=45)
        log1, created1 = InstrumentHistoryLog.objects.get_or_create(
            library_instrument=instrument,
            event_category=InstrumentHistoryLog.EVENT_OUT_FOR_REPAIR,
            event_date=repair_out_date,
            defaults={
                'notes': 'Sent to repair shop - sticky valve/key reported'
            }
        )
        if created1:
            logs_created += 1
        
        # Returned from repair
        repair_return_date = today - timedelta(days=30)
        log2, created2 = InstrumentHistoryLog.objects.get_or_create(
            library_instrument=instrument,
            event_category=InstrumentHistoryLog.EVENT_RETURNED_FROM_REPAIR,
            event_date=repair_return_date,
            defaults={
                'notes': 'Returned from repair - cleaned and serviced, new pads installed'
            }
        )
        if created2:
            logs_created += 1
            print(f"  ✓ Repair: {instrument.instrument.name} {instrument.serial_number}")
    
    # 4. Add some location checks
    print("\n--- Creating Location Checks ---")
    check_instruments = all_instruments[13:16] if len(all_instruments) > 13 else []
    
    for instrument in check_instruments:
        check_date = today - timedelta(days=15)
        log, created = InstrumentHistoryLog.objects.get_or_create(
            library_instrument=instrument,
            event_category=InstrumentHistoryLog.EVENT_LOCATION_CHECK,
            event_date=check_date,
            defaults={
                'notes': 'Location verified - instrument in storage room A3'
            }
        )
        if created:
            logs_created += 1
            print(f"  ✓ Location Check: {instrument.instrument.name} {instrument.serial_number}")
    
    # 5. Add one instrument that needs repair
    if len(all_instruments) > 16:
        print("\n--- Creating Instruments Needing Repair ---")
        needs_repair = all_instruments[16]
        needs_repair.status = LibraryInstrument.STATUS_NEEDS_REPAIR
        needs_repair.comments = (needs_repair.comments or "") + " - Needs valve alignment"
        needs_repair.save()
        
        log, created = InstrumentHistoryLog.objects.get_or_create(
            library_instrument=needs_repair,
            event_category=InstrumentHistoryLog.EVENT_RENTAL_NOTE,
            event_date=today - timedelta(days=3),
            defaults={
                'notes': 'Marked as needing repair - valve sticking during rehearsal'
            }
        )
        if created:
            logs_created += 1
            print(f"  ✓ Needs Repair: {needs_repair.instrument.name} {needs_repair.serial_number}")
    
    # 6. Add a recent return
    if len(all_instruments) > 17 and members:
        print("\n--- Creating Recent Returns ---")
        recent_return = all_instruments[17]
        return_date = today - timedelta(days=5)
        
        log, created = InstrumentHistoryLog.objects.get_or_create(
            library_instrument=recent_return,
            event_category=InstrumentHistoryLog.EVENT_RETURNED_FROM_LOAN,
            event_date=return_date,
            defaults={
                'notes': f'Returned from loan - instrument in good condition'
            }
        )
        if created:
            logs_created += 1
            print(f"  ✓ Recent Return: {recent_return.instrument.name} {recent_return.serial_number}")
    
    print(f"\n=== Total history logs created: {logs_created} ===")
    return logs_created


if __name__ == "__main__":
    print("=" * 60)
    print("Creating Instrument Library Data")
    print("=" * 60)
    
    instrument_count = create_instrument_library_data()
    
    print("\n" + "=" * 60)
    print("Creating Rental History Logs")
    print("=" * 60)
    
    log_count = create_rental_history_logs()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Library instruments created: {instrument_count}")
    print(f"History logs created: {log_count}")
    print("\nDone! Check the admin panel to view the data.")
