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
- Find and replace all instances of `"live_revision": [id or null]` with `"live_revision": null` in the json file
- Find and replace all instances of `"latest_revision": [id or null]` with `"latest_revision": null` in the json file
- Run the following command to import the data into the local database
    `python manage.py loaddata <path_to_json_file>`
- Log in to the admin panel at [http://localhost:8000/admin](http://localhost:8000/admin) to verify that the data has been imported successfully
- Delete the default "Welcome to your new Wagtail site!" page if it exists
- Navigate to the [sites settings](https://blowcomotion.pythonanywhere.com/admin/sites/) and change the localhost root page to the homepage of the imported data
