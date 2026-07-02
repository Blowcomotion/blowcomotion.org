"""
Tests for Section model methods.
"""

from django.test import TestCase

from blowcomotion.models import Instrument, Member, MemberInstrument, Section


class SectionGetMembersTests(TestCase):
    """Test cases for Section.get_members() method"""

    def setUp(self):
        """Set up test data"""
        self.brass_section = Section.objects.create(name='Brass')
        self.woodwind_section = Section.objects.create(name='Woodwind')
        self.trumpet = Instrument.objects.create(name='Trumpet', section=self.brass_section)
        self.trombone = Instrument.objects.create(name='Trombone', section=self.brass_section)
        self.clarinet = Instrument.objects.create(name='Clarinet', section=self.woodwind_section)

    def test_includes_member_with_matching_primary_instrument(self):
        member = Member.objects.create(
            first_name='John', last_name='Doe', email='john@example.com',
            primary_instrument=self.trumpet, is_active=True
        )

        self.assertIn(member, self.brass_section.get_members())

    def test_includes_member_with_matching_additional_instrument(self):
        member = Member.objects.create(
            first_name='Jane', last_name='Smith', email='jane@example.com',
            primary_instrument=self.clarinet, is_active=True
        )
        MemberInstrument.objects.create(member=member, instrument=self.trombone)

        self.assertIn(member, self.brass_section.get_members())

    def test_excludes_member_from_other_section(self):
        member = Member.objects.create(
            first_name='Bob', last_name='Jones', email='bob@example.com',
            primary_instrument=self.clarinet, is_active=True
        )

        self.assertNotIn(member, self.brass_section.get_members())

    def test_excludes_inactive_member(self):
        member = Member.objects.create(
            first_name='Alice', last_name='Brown', email='alice@example.com',
            primary_instrument=self.trumpet, is_active=False
        )

        self.assertNotIn(member, self.brass_section.get_members())

    def test_does_not_duplicate_member_matching_on_both_instrument_fields(self):
        member = Member.objects.create(
            first_name='Charlie', last_name='Wilson', email='charlie@example.com',
            primary_instrument=self.trumpet, is_active=True
        )
        MemberInstrument.objects.create(member=member, instrument=self.trombone)

        self.assertEqual(list(self.brass_section.get_members()), [member])
