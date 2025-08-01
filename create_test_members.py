#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blowcomotion.settings.dev')
django.setup()

from blowcomotion.models import Section, Member, Instrument, MemberInstrument
from datetime import date

print("Sections available:")
sections = Section.objects.all().order_by('name')
for section in sections:
    print(f"- {section.name} (ID: {section.id})")

if not sections:
    print("No sections found in database!")
    exit(1)

# Define test member pools for different sections
test_member_pools = {
    "High Brass": [
        {"first_name": "Sarah", "last_name": "Johnson", "email": "sarah.j@email.com"},
        {"first_name": "Michael", "last_name": "Chen", "email": "michael.c@email.com"},
        {"first_name": "Emma", "last_name": "Rodriguez", "email": "emma.r@email.com"},
        {"first_name": "David", "last_name": "Thompson", "email": "david.t@email.com"},
        {"first_name": "Ashley", "last_name": "Williams", "email": "ashley.w@email.com"},
    ],
    "Low Brass": [
        {"first_name": "James", "last_name": "Brown", "email": "james.b@email.com"},
        {"first_name": "Maria", "last_name": "Garcia", "email": "maria.g@email.com"},
        {"first_name": "Robert", "last_name": "Davis", "email": "robert.d@email.com"},
        {"first_name": "Jennifer", "last_name": "Miller", "email": "jennifer.m@email.com"},
        {"first_name": "Christopher", "last_name": "Wilson", "email": "chris.w@email.com"},
    ],
    "Woodwinds": [
        {"first_name": "Amanda", "last_name": "Taylor", "email": "amanda.t@email.com"},
        {"first_name": "Kevin", "last_name": "Anderson", "email": "kevin.a@email.com"},
        {"first_name": "Lisa", "last_name": "Thomas", "email": "lisa.t@email.com"},
        {"first_name": "Brian", "last_name": "Jackson", "email": "brian.j@email.com"},
        {"first_name": "Rachel", "last_name": "White", "email": "rachel.w@email.com"},
        {"first_name": "Daniel", "last_name": "Harris", "email": "daniel.h@email.com"},
    ],
    "Percussion": [
        {"first_name": "Marcus", "last_name": "Clark", "email": "marcus.c@email.com"},
        {"first_name": "Stephanie", "last_name": "Lewis", "email": "stephanie.l@email.com"},
        {"first_name": "Tyler", "last_name": "Robinson", "email": "tyler.r@email.com"},
        {"first_name": "Nicole", "last_name": "Walker", "email": "nicole.w@email.com"},
    ],
    # Generic names for any other sections
    "default": [
        {"first_name": "Alex", "last_name": "Smith", "email": "alex.s@email.com"},
        {"first_name": "Jamie", "last_name": "Jones", "email": "jamie.j@email.com"},
        {"first_name": "Taylor", "last_name": "Brown", "email": "taylor.b@email.com"},
        {"first_name": "Jordan", "last_name": "Davis", "email": "jordan.d@email.com"},
        {"first_name": "Casey", "last_name": "Wilson", "email": "casey.w@email.com"},
    ]
}

# Dictionary to store created members by section
section_members_created = {}

# Create members for each section dynamically
for section in sections:
    print(f"\nCreating members for {section.name} section...")
    
    # Get member pool for this section (or default if not found)
    member_pool = test_member_pools.get(section.name, test_member_pools["default"])
    
    section_members = []
    for i, member_data in enumerate(member_pool):
        # Try to find existing member first by name and original email
        existing_member = Member.objects.filter(
            first_name=member_data["first_name"],
            last_name=member_data["last_name"]
        ).first()
        
        if existing_member:
            print(f"Found existing member: {existing_member.first_name} {existing_member.last_name}")
            member = existing_member
        else:
            # Create new member with section-specific email
            email = member_data["email"].replace("@", f".{section.name.lower().replace(' ', '')}@")
            
            member, created = Member.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": member_data["first_name"],
                    "last_name": member_data["last_name"],
                    "join_date": date(2024, 1 + (i % 12), 15),  # Spread join dates across months
                    "is_active": True,
                }
            )
            if created:
                print(f"Created: {member.first_name} {member.last_name}")
            else:
                print(f"Already exists: {member.first_name} {member.last_name}")
        
        section_members.append(member)
    
    section_members_created[section] = section_members

# Now assign instruments to members for each section
print("\nAssigning instruments to members...")

total_members_created = 0
for section, members in section_members_created.items():
    print(f"\nProcessing {section.name} section...")
    
    # Get instruments for this section
    section_instruments = Instrument.objects.filter(section=section)
    print(f"Available instruments: {[inst.name for inst in section_instruments]}")
    
    if section_instruments:
        # Assign instruments to members
        for i, member in enumerate(members):
            # Rotate through available instruments
            instrument = section_instruments[i % len(section_instruments)]
            member_instrument, created = MemberInstrument.objects.get_or_create(
                member=member,
                instrument=instrument,
            )
            if created:
                print(f"Assigned {instrument.name} to {member.first_name} {member.last_name}")
            else:
                print(f"{member.first_name} {member.last_name} already has {instrument.name}")
    else:
        print(f"No instruments found for {section.name} section")
    
    total_members_created += len(members)

print("\nTest members and instrument assignments created successfully!")
for section, members in section_members_created.items():
    print(f"{section.name}: {len(members)} members")
print(f"Total members across all sections: {total_members_created}")
