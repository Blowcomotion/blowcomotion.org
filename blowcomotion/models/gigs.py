import datetime

from django.db import models


class CachedGig(models.Model):
    """
    Model for caching gig data from the Gig-O-Matic API.
    
    Instead of making API calls on every page load, gig data is synced
    periodically (via cron) and stored in the database for faster access.
    
    Attributes:
        gig_id: The unique ID from Gig-O-Matic
        title: Gig title
        date: Date of the gig
        time: Time of the gig (stored separately for querying)
        address: Location/address of the gig
        gig_status: Status from API (e.g., 'confirmed', 'unconfirmed')
        band: Band name from the API
        raw_data: Full JSON response from the API for this gig
        last_synced: When this record was last updated from the API
    """
    gig_id = models.IntegerField(unique=True, db_index=True)
    title = models.CharField(max_length=500)
    date = models.DateField(db_index=True)
    time = models.TimeField(null=True, blank=True)
    address = models.TextField(blank=True, default='')
    gig_status = models.CharField(max_length=50, db_index=True)
    band = models.CharField(max_length=255, db_index=True)
    raw_data = models.JSONField(default=dict)
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cached Gig"
        verbose_name_plural = "Cached Gigs"
        ordering = ['date', 'time']
        indexes = [
            models.Index(fields=['date', 'gig_status', 'band']),
        ]

    def __str__(self):
        return f"{self.title} ({self.date})"

    @classmethod
    def get_gigs_for_date(cls, date_str, band=None, status='confirmed'):
        """Get confirmed gigs for a specific date."""
        from django.conf import settings

        band = band or getattr(settings, 'GIGO_BAND_NAME', 'Blowcomotion')
        return cls.objects.filter(
            date=date_str,
            band__iexact=band,
            gig_status__iexact=status,
        )

    @classmethod
    def get_upcoming_gigs(cls, band=None, status='confirmed'):
        """Get all upcoming confirmed gigs from today onwards."""
        from django.conf import settings

        band = band or getattr(settings, 'GIGO_BAND_NAME', 'Blowcomotion')
        return cls.objects.filter(
            date__gte=datetime.date.today(),
            band__iexact=band,
            gig_status__iexact=status,
        ).order_by('date', 'time')

    @classmethod
    def get_gig_by_id(cls, gig_id):
        """Get a single gig by its Gig-O-Matic ID."""
        try:
            return cls.objects.get(gig_id=gig_id)
        except cls.DoesNotExist:
            return None

    def to_api_format(self):
        """Return the gig data in the same format as the API response."""
        return self.raw_data if self.raw_data else {
            'id': self.gig_id,
            'title': self.title,
            'date': self.date.isoformat(),
            'address': self.address,
            'gig_status': self.gig_status,
            'band': self.band,
        }
