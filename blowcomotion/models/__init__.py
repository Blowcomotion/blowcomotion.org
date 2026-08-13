# Models for the domain apps (gigs, attendance, charts, instruments, members) live here,
# not in those apps, because centralizing them here during the #312 hybrid-app split avoided
# migration/content-type risk on existing production data. That constraint doesn't apply to
# apps that don't exist yet — a genuinely new domain app going forward may define its own
# models.py/migrations with its own tables.

from blowcomotion.models.admin_tools import AdminToolUsage
from blowcomotion.models.attendance import AttendanceRecord
from blowcomotion.models.band import Instrument, Section, SectionInstructor
from blowcomotion.models.core import (
    CustomImage,
    CustomRendition,
    NotificationBanner,
    SiteSettings,
    get_default_expiration_date,
)
from blowcomotion.models.gigs import CachedGig
from blowcomotion.models.instruments import (
    Equipment,
    EquipmentPhoto,
    InstrumentHistoryLog,
    InstrumentRentalNagLog,
    InstrumentStorageLocation,
    LibraryInstrument,
    LibraryInstrumentPhoto,
)
from blowcomotion.models.members import (
    EmailChangeToken,
    Member,
    MemberInstrument,
    PasswordSetToken,
)
from blowcomotion.models.music import (
    Chart,
    Event,
    EventSetlistSong,
    Song,
    SongConductor,
    SongSoloist,
    SongVideo,
)
from blowcomotion.models.pages import (
    BasePage,
    BlankCanvasPage,
    WikiAuthor,
    WikiIndexPage,
    WikiPage,
)
from blowcomotion.models.submissions import (
    BaseFormSubmission,
    BookingFormSubmission,
    ContactFormSubmission,
    DonateFormSubmission,
    FeedbackFormSubmission,
    InstrumentRentalRequestSubmission,
    JoinBandFormSubmission,
)
