# Blowcomotion.org Website

Blowcomotion.org is a Django/Wagtail CMS website for a band called "Blowcomotion" that manages attendance tracking, member birthdays, events, and content management.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap, build, and test the repository:
- Create Python virtual environment: `python -m venv venv` (takes 3 seconds)
- Activate virtual environment: `source venv/bin/activate` (Linux/macOS) or `venv\Scripts\activate` (Windows)
- Install dependencies: `pip install -r requirements.txt` -- takes 45 seconds. NEVER CANCEL.
- Install isort for pre-commit hooks: `pip install isort` (takes 5 seconds)
- Run database migrations: `python manage.py migrate` -- takes 10 seconds. NEVER CANCEL.
- Create superuser: `python manage.py createsuperuser` (interactive, takes 30 seconds)

### Development server:
- Start server: `python manage.py runserver` -- starts immediately
- Access homepage: http://localhost:8000/
- Access admin panel: http://localhost:8000/admin/
- ALWAYS run the bootstrapping steps first before starting the server

### Static files and production:
- Collect static files: `python manage.py collectstatic --noinput` -- takes 1 second. NEVER CANCEL.
- ALWAYS run `python manage.py collectstatic` after changes to CSS, JavaScript, or images for production deployment

### Code quality:
- Check import sorting: `isort --check-only blowcomotion/ --diff` (takes 1 second)
- Fix import sorting: `isort blowcomotion/` (takes 1 second)
- ALWAYS run `isort blowcomotion/` before committing changes to ensure proper import organization

## Validation

- ALWAYS manually validate any new code by visiting the running application in a browser
- Test core functionality:
  - Homepage loads at http://localhost:8000/
  - Admin panel accessible at http://localhost:8000/admin/ with superuser credentials
  - Attendance system at http://localhost:8000/attendance/ 
  - Birthdays feature at http://localhost:8000/birthdays/
- ALWAYS test complete end-to-end scenarios after making changes
- ALWAYS run `isort blowcomotion/` before committing or the pre-commit hook will auto-fix imports

## Key Features & URLs

### Core Application Features:
- **Attendance Tracking**: `/attendance/` - Records band member attendance for rehearsals and performances
- **Birthday Management**: `/birthdays/` - Displays upcoming and recent member birthdays  
- **Admin Panel**: `/admin/` - Wagtail CMS admin for content and band management
- **Band Stuff**: Admin section includes Events, Sections, Instruments, Members, Songs, Charts, Attendance Records

### Authentication:
- Admin panel requires superuser account
- Attendance and birthday pages use HTTP Basic Auth (configured in Wagtail Admin > Settings)

## Technology Stack

### Core Technologies:
- **Django 5.1.6**: Web framework
- **Wagtail 6.4.1**: CMS for content management
- **Python 3.12+**: Programming language
- **SQLite**: Database (development)
- **Bootstrap**: CSS framework
- **SASS/SCSS**: CSS preprocessing with django-libsass

### Key Dependencies:
- django-compressor: Asset compression and SASS compilation
- django-livereload-server: Development live reload
- wagtailmedia: Media file management
- wagtailtwbsicons: Bootstrap icons for Wagtail
- requests: HTTP client for GigoGig API integration

## Project Structure

### Important Directories:
- `blowcomotion/`: Main Django app with models, views, templates
- `blowcomotion/settings/`: Settings split (dev.py, production.py, base.py)
- `blowcomotion/templates/`: HTML templates
- `blowcomotion/static/`: CSS, JS, images
- `blowcomotion/tests/`: Test files
- `scripts/`: Utility scripts including pre-commit hooks
- `requirements.txt`: Python dependencies

### Key Files:
- `manage.py`: Django management commands
- `pyproject.toml`: isort configuration for import sorting
- `scripts/pre-commit-isort.sh`: Pre-commit hook for automatic import sorting

## Database & Models

### Key Models:
- **Member**: Band member information including birthdays
  - `primary_instrument`: ForeignKey to Instrument - the member's main instrument (single choice)
  - `additional_instruments`: ManyToMany through MemberInstrument - extra instruments the member plays
  - Members appear in only ONE section based on their primary_instrument
  - Wagtail search indexing is disabled for Member model (search works via Django queries in admin)
- **MemberInstrument**: Through model linking Members to additional instruments
- **Instrument**: Musical instruments with section association
- **AttendanceRecord**: Records attendance for rehearsals/performances  
- **Section**: Band sections (Woodwinds, High Brass, etc.)
- **Event**: Band events and performances
- **Song/Chart**: Music library management
- **SiteSettings**: Site configuration and access control

### Database Operations:
- Migrations are in `blowcomotion/migrations/`
- Run `python manage.py migrate` after model changes
- Development uses SQLite database (`db.sqlite3`)
- **Important**: Migration 0076 migrates existing instruments to primary/additional structure

## API Integration

### GigoGig API:
- Integrates with external GigoGig API for performance data
- Environment variables: `GIGO_API_URL`, `GIGO_API_KEY`
- Local API endpoint: `/attendance/gigs-for-date/?date=YYYY-MM-DD`
- Caching: 10-minute cache for performance

## Development Workflow

### Making Changes:
1. Activate virtual environment: `source venv/bin/activate`
2. Start development server: `python manage.py runserver`
3. Make code changes
4. Test functionality manually in browser
5. Check import sorting: `isort --check-only blowcomotion/ --diff`
6. Fix imports if needed: `isort blowcomotion/`
7. Run migrations if models changed: `python manage.py migrate`
8. Collect static files if CSS/JS changed: `python manage.py collectstatic --noinput`

### Pre-commit Hook:
- Automatic import sorting with isort
- Located at `scripts/pre-commit-isort.sh`
- Runs automatically on git commit
- Configuration in `pyproject.toml`

## Common Tasks

### Creating Superuser:
```bash
python manage.py createsuperuser
# Follow prompts for username, email, password
```

### Accessing Admin Features:
- **Band Management**: Wagtail Admin > Band Stuff
- **Site Settings**: Wagtail Admin > Settings > Site Settings
- **Form Submissions**: Wagtail Admin > Form Submissions  
- **Page Management**: Wagtail Admin > Pages

### Managing Members:
- **Adding Members**: Wagtail Admin > Band Stuff > Members > Add Member
  - Set `primary_instrument`: The member's main instrument (required for section assignment)
  - Set `additional_instruments`: Any extra instruments the member plays (optional)
  - Members appear in attendance by their primary instrument's section only
- **Editing Members**: Update primary/additional instruments as needed
- **Data Migration**: Migration 0076 automatically converted old instrument data to new structure


### Static File Management:
- Development: Files served automatically from `blowcomotion/static/`
- Production: Run `python manage.py collectstatic` to collect files to `static/`
- SASS compilation happens automatically via django-compressor

## Environment Variables

Optional configuration:
- `DJANGO_SETTINGS_MODULE`: Default is `blowcomotion.settings.dev`
- `GIGO_API_URL`: GigoGig API endpoint (default: `http://localhost:8000/api`)
- `GIGO_API_KEY`: API key for GigoGig integration

## Testing

### Test Files:
- `blowcomotion/tests/test_attendance_views.py`: Attendance system tests
- `blowcomotion/tests/test_birthday_views.py`: Birthday feature tests

### Running Tests:
Tests require Django settings configuration. Manual validation is primary testing method:
1. Start development server
2. Test each major feature in browser
3. Verify attendance tracking works
4. Check birthday display functionality
5. Test admin panel operations

## Common Commands Reference

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
pip install isort
python manage.py migrate
python manage.py createsuperuser

# Development
python manage.py runserver
python manage.py collectstatic --noinput
isort blowcomotion/
isort --check-only blowcomotion/ --diff

# URLs to test
# http://localhost:8000/ - Homepage
# http://localhost:8000/admin/ - Admin panel
# http://localhost:8000/attendance/ - Attendance tracking
# http://localhost:8000/birthdays/ - Birthday display
```

## Timing Expectations

- Virtual environment creation: 3 seconds
- Package installation: 45 seconds - NEVER CANCEL
- Database migrations: 10 seconds - NEVER CANCEL  
- Server startup: immediate
- Static file collection: 1 second - NEVER CANCEL
- Import sorting: 1 second

Always wait for commands to complete. Build times are fast but package installation requires patience.