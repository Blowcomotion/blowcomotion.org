# blowcomotion.org
Stores the codebase for the blowcomotion.org website

**Live Site:** [https://blowcomotion.org](https://blowcomotion.org)

**Template Demo:** [https://themewagon.github.io/Djoz/index.html](https://themewagon.github.io/Djoz/index.html)

The templates for this codebase are derived from the [Djoz theme](https://themewagon.com/themes/free-bootstrap-responsive-personal-portfolio-template-djoz/)


## Installation
- Clone the repository

    `git clone <repository-url>`

- Navigate to the project directory
    `cd blowcomotion.org`
- Create a virtual environment
    `python -m venv venv`
- Activate the virtual environment
    - On Windows:
        `venv\Scripts\activate`
    - On macOS/Linux:
        `source venv/bin/activate`
- Install the required packages
    `pip install -r requirements.txt`
- Run database migrations
    `python manage.py migrate`
- Create a superuser account
    `python manage.py createsuperuser`

## Development Tools

### Pre-commit Hook for Import Sorting

This project includes a pre-commit git hook that automatically sorts Python imports using `isort` to maintain consistent code formatting.

#### Pre-commit Hook Features

- **Automatic import sorting**: Runs `isort` on all staged Python files before each commit
- **Smart behavior**: Only processes files that need changes and re-stages them
- **User-friendly**: Provides clear feedback and allows review of changes
- **Django-optimized**: Uses Django-specific import grouping and formatting rules

#### How It Works

1. When you run `git commit`, the hook automatically activates
2. It checks all staged `.py` files for import order issues
3. If issues are found, it fixes them and re-stages the files
4. The commit is paused to allow you to review the changes
5. Run `git commit` again to complete the commit with properly sorted imports

#### Configuration

The import sorting behavior is configured in `pyproject.toml`:

```toml
[tool.isort]
profile = "django"
multi_line_output = 3
include_trailing_comma = true
line_length = 88
known_first_party = "blowcomotion,search,website"
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "DJANGO", "FIRSTPARTY", "LOCALFOLDER"]
```

#### Manual Usage

You can also run `isort` manually:

```bash
# Check if files need sorting
isort --check-only blowcomotion/

# Fix import order
isort blowcomotion/
```

#### Requirements

- `isort` must be installed: `pip install isort`
- The hook is automatically executable after cloning the repository

#### Development Workflow

With the pre-commit hook enabled, your typical development workflow becomes:

```bash
# Make changes to Python files
git add blowcomotion/views.py

# Attempt to commit
git commit -m "Update views"

# If imports need fixing, the hook will:
# 1. Automatically fix import order
# 2. Re-stage the fixed files
# 3. Display a message asking you to review and commit again

# Review the changes (optional)
git diff --cached

# Commit again (will succeed if no further issues)
git commit -m "Update views"
```

This ensures that all Python code follows consistent import formatting standards automatically.

## Run the web app

- Start the development server
    `python manage.py runserver`
- Open your web browser and go to the [homepage](http://localhost:8000)
- You can access the admin panel at [http://localhost:8000/admin](http://localhost:8000/admin)
- To stop the server, press `Ctrl+C` in the terminal

## Import data from the website to the local database
- Navigate to the live website admin [data dump page](https://www.blowcomotion.org/admin/dump_data/)
- Save the json file to your local machine
- Navigate to the project directory
    `cd blowcomotion.org`
- Find and replace all instances of `"live_revision": [id or null]` with `"live_revision": null,` in the json file 
    - Using VS Code:
        - Open the json file and select the Search button
        - Click on `.*` button in the search bar to enable regex option
        - In the Search box, paste the following `"live_revision":.*` 
        - In Replace box, enter `"live_revision": null,`
        - Click the Replace All button
        - Repeat these steps again, searching for `"latest_revision": [id or null]` and replacing all instances with `"latest_revision": null,`
- Run the following command to import the data into the local database
    `python manage.py loaddata <path_to_json_file>`
- Log in to the admin panel at [http://localhost:8000/admin](http://localhost:8000/admin) to verify that the data has been imported successfully
- Navigate to [page explorer](http://localhost:8000/admin/pages/) Delete the default "Welcome to your new Wagtail site!" page if it exists in the admin panel
- Navigate to the [sites settings](http://localhost:8000/admin/sites/) and change the localhost root page to the homepage of the imported data

## Production Deployment

When deploying to production, always run:

- `python manage.py collectstatic` - Collects all static files (CSS, JS, images) for production
- `python manage.py migrate` - Applies any new database migrations

**Important**: Run `collectstatic` after any changes to static files (CSS, JavaScript, images) to ensure they're available in production.

## Database Schema

### Member Model (Updated October 2025)

The Member model was refactored to better represent instrument relationships:

#### Instrument Fields

- **`primary_instrument`** (ForeignKey): The member's main instrument - determines which section they appear in for attendance
- **`additional_instruments`** (ManyToMany through MemberInstrument): Any extra instruments the member can play

#### Key Changes

- Members now appear in **only ONE section** during attendance tracking (based on primary_instrument)
- The old `instruments` many-to-many field was split into primary + additional
- Migration 0076 automatically migrated existing data: first instrument → primary, rest → additional
- Admin search for Members uses Django queries instead of Wagtail FTS indexing for better SQLite compatibility

#### Adding/Editing Members

1. Navigate to **Wagtail Admin > Band Stuff > Members**
2. Set the **Primary Instrument** - this determines their section for attendance
3. Optionally add **Additional Instruments** they can also play
4. The primary instrument should NOT be listed in additional instruments

## Features

### Attendance Tracker

The attendance tracking system allows band leaders to record and manage attendance for rehearsals and performances with integrated gig management.

#### Key Features

- **Section-based tracking**: Record attendance by band section (Woodwinds, High Brass, etc.)
- **Single section assignment**: Each member appears in only one section based on their primary instrument
- **Member and guest support**: Track both band members and guests/visitors
- **Event types**: Differentiate between rehearsals and performances
- **Gig integration**: Automatically fetch and select from confirmed gigs when recording performance attendance
- **Smart gig selection**: Gigs are filtered by date, band (Blowcomotion), and confirmation status
- **Dynamic form behavior**: Event type selection shows/hides relevant fields (gig selection for performances, notes for rehearsals)
- **Comprehensive reporting**: View attendance statistics and trends
- **Admin management**: Full CRUD operations for attendance records through Wagtail admin

#### Gig Integration (New Feature)

The attendance system now integrates with the GigoGig API to provide seamless gig selection:

- **Automatic gig fetching**: When "Performance" is selected, available gigs are loaded for the chosen date
- **Real-time updates**: Gig options update dynamically when the date changes
- **Smart filtering**: Only shows confirmed Blowcomotion gigs for the selected date
- **Caching**: Gig data is cached for 10 minutes to improve performance
- **Fallback handling**: Gracefully handles API errors and provides fallback options

#### How to Use

1. **Recording Attendance**: Access the attendance capture interface at `/attendance/`
2. **Section Navigation**: Select a band section to record attendance for that group
3. **Date Selection**: Choose the date for the attendance session
4. **Event Type**:
   - Select "Rehearsal" for practice sessions (shows notes field)
   - Select "Performance" for gigs (shows gig selection dropdown)
5. **Gig Selection** (Performances only): Choose from available confirmed gigs for the selected date
6. **Member Selection**: Check off members who attended
7. **Guest Entry**: Add names of guests/visitors (one per line)
8. **Submit**: Record attendance with automatic event information

#### Technical Features

- **API Integration**: Connects to GigoGig API for real-time gig data
- **JavaScript Enhancement**: Dynamic form behavior with HTMX for seamless user experience
- **Caching Strategy**: Intelligent caching to reduce API calls and improve performance
- **Error Handling**: Robust error handling for network issues and API failures

#### Admin Management

- Navigate to **Wagtail Admin > Band Stuff > Attendance Records**
- View, edit, and delete attendance records
- Filter by date, member, or search notes
- Export data for external analysis
- View gig information in attendance notes

#### Security

- Protected by HTTP Basic Authentication
- Password configurable through **Wagtail Admin > Settings > Site Settings > Access Control**

### Birthdays Function

The birthdays feature displays upcoming band member birthdays to help celebrate and recognize members.

#### Birthday Features

- **Upcoming birthdays**: Shows members with birthdays in the current month
- **Privacy-aware**: Only displays month/day, respects member privacy
- **Mobile-friendly**: Responsive design for all devices
- **Admin integration**: Birthday data managed through member profiles

#### How to Access

1. **Access**: Navigate to `/birthdays/` to view the birthdays page
2. **Display**: Shows members with birthdays in the current month
3. **Information**: Displays member name, birthday (month/day), and photo if available

#### Birthday Admin Management

- **Member Profiles**: Add birthday information in Wagtail Admin > Band Stuff > Members
- **Fields**: `birth_month`, `birth_day`, and optional `birth_year`
- **Privacy**: Birth year is optional and not displayed publicly

#### Birthday Security

- Protected by HTTP Basic Authentication  
- Password configurable through **Wagtail Admin > Settings > Site Settings > Access Control**

## Environment Variables

The following environment variables can be configured:

- `GIGO_API_URL` - API endpoint for GIGO integration (default: `http://localhost:8000/api`)
- `GIGO_API_KEY` - API key for GIGO integration (required for gig features)

### GigoGig API Integration

The attendance system integrates with the GigoGig API to fetch gig information:

#### API Endpoints Used

- **GET /gigs** - Fetches all gigs, filtered client-side for date/band/status
- **GET /gigs/{id}** - Fetches specific gig details (used for attendance notes)

#### API Configuration

1. Set the `GIGO_API_URL` environment variable to your GigoGig API base URL
2. Set the `GIGO_API_KEY` environment variable with your API key
3. The system will automatically fetch gigs when recording performance attendance

#### Local API Endpoint

The application also provides a local API endpoint for gig data:

- **GET /attendance/gigs-for-date/?date=YYYY-MM-DD** - Returns filtered gigs for a specific date

This endpoint is used by the JavaScript frontend and includes caching for performance.

## Admin Configuration

Site settings, including access control passwords, are configured through the Wagtail admin interface:

1. Access **Wagtail Admin > Settings > Site Settings**
2. Configure passwords in the **Access Control** section
3. Set email recipients for forms in the **Form Email Recipients** section
4. Update donation links in the **Donation Links** section
5. Manage social media links and site branding

## Recent Changes

### Member Model Refactoring (October 2025)

The Member model was refactored to improve instrument management and section assignment. See [MEMBER_MODEL_REFACTOR.md](MEMBER_MODEL_REFACTOR.md) for complete details.

**Key changes:**
- Split instruments into `primary_instrument` (single) and `additional_instruments` (multiple)
- Members now appear in only one section during attendance based on primary instrument
- Migration 0076 automatically converted existing data
- Admin search uses Django queries instead of Wagtail FTS for better SQLite compatibility

**Breaking changes:**
- Attendance views now filter by `primary_instrument` instead of many-to-many `instruments`
- Templates display `member.primary_instrument` instead of looping through `member.instruments.all`
- Forms require setting primary instrument for proper section assignment
