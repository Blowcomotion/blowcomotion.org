"""
Tests for Equipment model validation.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from blowcomotion.models import Equipment, InstrumentStorageLocation, Member


class EquipmentMemberAssignmentTests(TestCase):
    """Equipment can be assigned to a member instead of a storage location."""

    def setUp(self):
        self.member = Member.objects.create(
            first_name='Matt', last_name='M', email='matt@example.com', is_active=True
        )
        self.location = InstrumentStorageLocation.objects.create(name='Storage Shed')

    def test_can_assign_equipment_to_a_member(self):
        equipment = Equipment.objects.create(name='Canopy', member=self.member)

        self.assertEqual(equipment.member, self.member)

    def test_rejects_both_member_and_storage_location(self):
        equipment = Equipment(name='Canopy', member=self.member, storage_location=self.location)

        with self.assertRaises(ValidationError):
            equipment.clean()
