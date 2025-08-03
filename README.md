# blowcomotion.org
Stores the codebase for the blowcomotion.org website

The templates for this codebase are derived from [here](https://themewagon.com/themes/free-bootstrap-responsive-personal-portfolio-template-djoz/)


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

## Run the web app

- Start the development server
    `python manage.py runserver`
- Open your web browser and go to the [homepage](http://localhost:8000)
- You can access the admin panel at [http://localhost:8000/admin](http://localhost:8000/admin)
- To stop the server, press `Ctrl+C` in the terminal

## Import data from the website to the local database

- Navigate to the website admin [data dump page](http://localhost:8000//admin/dump_data/)
- Save the json file to your local machine
- Navigate to the project directory
    `cd blowcomotion.org`
- Find and replace all instances of `"live_revision": [id or null]` with `"live_revision": null,` in the json file
- Find and replace all instances of `"latest_revision": [id or null]` with `"latest_revision": null,` in the json file
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

## Features

### Attendance Tracker

The attendance tracking system allows band leaders to record and manage attendance for rehearsals and performances.

#### Key Features

- **Section-based tracking**: Record attendance by band section (Woodwinds, High Brass, etc.)
- **Member and guest support**: Track both band members and guests/visitors
- **Event types**: Differentiate between rehearsals and performances
- **Comprehensive reporting**: View attendance statistics and trends
- **Admin management**: Full CRUD operations for attendance records through Wagtail admin

#### How to Use

1. **Recording Attendance**: Access the attendance capture interface at `/attendance/`
2. **Section Navigation**: Select a band section to record attendance for that group
3. **Date Selection**: Choose the date for the attendance session
4. **Event Type**: Specify whether it's a rehearsal or performance
5. **Member Selection**: Check off members who attended
6. **Guest Entry**: Add names of guests/visitors (one per line)
7. **Reports**: View detailed attendance reports and statistics

#### Admin Management

- Navigate to **Wagtail Admin > Band Stuff > Attendance Records**
- View, edit, and delete attendance records
- Filter by date, member, or search notes
- Export data for external analysis

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
- `GIGO_API_KEY` - API key for GIGO integration

## Admin Configuration

Site settings, including access control passwords, are configured through the Wagtail admin interface:

1. Access **Wagtail Admin > Settings > Site Settings**
2. Configure passwords in the **Access Control** section
3. Set email recipients for forms in the **Form Email Recipients** section
4. Update donation links in the **Donation Links** section
5. Manage social media links and site branding
