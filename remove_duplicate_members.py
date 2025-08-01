#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blowcomotion.settings.dev')
django.setup()

from blowcomotion.models import Member, MemberInstrument, AttendanceRecord
from collections import defaultdict

print("Checking for duplicate members...")

# Group members by first_name and last_name
member_groups = defaultdict(list)
for member in Member.objects.all():
    key = (member.first_name.lower(), member.last_name.lower())
    member_groups[key].append(member)

duplicates_found = 0
members_to_delete = []

print("\nDuplicate analysis:")
for (first_name, last_name), members in member_groups.items():
    if len(members) > 1:
        duplicates_found += 1
        print(f"\nFound {len(members)} members named '{first_name.title()} {last_name.title()}':")
        
        # Sort by ID to keep the oldest (first created)
        members.sort(key=lambda m: m.id)
        
        for i, member in enumerate(members):
            # Check if member has any relationships
            instrument_count = MemberInstrument.objects.filter(member=member).count()
            attendance_count = AttendanceRecord.objects.filter(member=member).count()
            
            status = "KEEP (oldest)" if i == 0 else "DELETE"
            print(f"  - ID: {member.id}, Email: {member.email}, "
                  f"Instruments: {instrument_count}, Attendance: {attendance_count} [{status}]")
            
            # Mark duplicates for deletion (keep the first/oldest one)
            if i > 0:
                members_to_delete.append(member)

if duplicates_found == 0:
    print("No duplicate members found!")
    exit(0)

print(f"\nSummary:")
print(f"- Found {duplicates_found} sets of duplicate members")
print(f"- {len(members_to_delete)} duplicate members will be deleted")

# Ask for confirmation
print("\nThis will permanently delete the duplicate members listed above.")
confirmation = input("Do you want to proceed? (yes/no): ").strip().lower()

if confirmation not in ['yes', 'y']:
    print("Operation cancelled.")
    exit(0)

print("\nDeleting duplicate members...")

# Delete duplicates
deleted_count = 0
for member in members_to_delete:
    try:
        # Check if member has any attendance records
        attendance_records = AttendanceRecord.objects.filter(member=member)
        if attendance_records.exists():
            print(f"Warning: {member.first_name} {member.last_name} (ID: {member.id}) has {attendance_records.count()} attendance records")
            # Transfer attendance records to the kept member if needed
            # For now, we'll just warn and skip deletion
            print(f"Skipping deletion of {member.first_name} {member.last_name} due to attendance records")
            continue
        
        # Delete member instruments first (if any)
        MemberInstrument.objects.filter(member=member).delete()
        
        # Delete the member
        member_name = f"{member.first_name} {member.last_name}"
        member.delete()
        print(f"Deleted: {member_name} (ID: {member.id})")
        deleted_count += 1
        
    except Exception as e:
        print(f"Error deleting {member.first_name} {member.last_name}: {str(e)}")

print(f"\nCompleted! Deleted {deleted_count} duplicate members.")

# Re-check for any remaining duplicates
print("\nVerifying cleanup...")
remaining_duplicates = 0
for (first_name, last_name), members in member_groups.items():
    current_members = Member.objects.filter(
        first_name__iexact=first_name, 
        last_name__iexact=last_name
    )
    if current_members.count() > 1:
        remaining_duplicates += 1

if remaining_duplicates == 0:
    print("✅ All duplicates successfully removed!")
else:
    print(f"⚠️  {remaining_duplicates} duplicate sets still remain (possibly due to attendance records)")
