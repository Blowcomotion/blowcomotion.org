from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.models import Orderable
from wagtail.search import index

from django.db import models

from blowcomotion.models.members import Member


class Section(ClusterableModel, index.Indexed):
    name = models.CharField(max_length=255)

    search_fields = [
        index.SearchField("name"),
    ]

    def get_members(self):
        """Active members whose primary or additional instrument belongs to this section."""
        return Member.objects.filter(
            is_active=True
        ).filter(
            models.Q(primary_instrument__section=self) |
            models.Q(additional_instruments__instrument__section=self)
        ).distinct()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Section"
        verbose_name_plural = "Sections"


class SectionInstructor(Orderable):
    section = ParentalKey("blowcomotion.Section", related_name="instructors")
    instructor = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)

    panels = [
        "instructor",
    ]


class Instrument(models.Model, index.Indexed):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    section = models.ForeignKey(
        "blowcomotion.Section",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    hide_from_rental = models.BooleanField(
        default=False,
        help_text=(
            "Hide this instrument type from the rental request form. Use for instruments "
            "we carry but don't offer for general rental — e.g. a bass clarinet added to "
            "inventory because a member brought their own, but too rare to offer to others."
        ),
    )
    hide_from_member_forms = models.BooleanField(
        default=False,
        help_text=(
            "Hide this instrument type from member profile and signup instrument selectors. "
            "Use for instruments members don't play but exist in inventory — e.g. a prop "
            "instrument or one not assigned to any section."
        ),
    )
    image = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    search_fields = [
        index.AutocompleteField("name"),
        index.SearchField("name"),
        index.SearchField("description"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Instrument Type"
        verbose_name_plural = "Instrument Types"
