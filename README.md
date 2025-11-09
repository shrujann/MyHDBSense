# MyHDBSense

**A Smart Singapore HDB/Resale Explorer & Amenities Tracker**  
*SC2006 Course Project*

![Languages](https://img.shields.io/badge/languages-HTML%2053.9%25%20%7C%20Python%2046.1%25https://img.shields.io/github/contributors/shrujann/MyHDBSense(https://github.com/shrujann/MyHDBSense/graphs/contributorshttps://img.shields.io/github/forks/shrujann/MyHDBSense(https://github.com/shrujann/MyHDBSense/forkshttps://img.shields.io/github/stars/shrujann/MyHDBSense(https://github.com/shrujann/MyHDBSense/stargazers

**MyHDBSense** is a web application designed for helping Singapore HDB (public housing) buyers and residents:
- **Find resale flats and amenities near any location**
- **Visualize important nearby features, including MRT, clinics, schools, parks, supermarkets, and more**
- **See maps, listings, scoring, and distance-based filtering, all in a modern UI**
- **Leverage Singapore public APIs (OneMap, LTA, Data.gov.sg) for up-to-date geo-information**

Built with **Django** (Python backend) and modern **HTML/CSS/JavaScript** for interactive maps and user experience.

***

## Features

- **Postal code search:** Enter a 6-digit postal code for instant nearby flat, amenity, and MRT mapping
- **Interactive map:** View flats and amenities on a Leaflet-powered map, with live markers, community data, and radius filtering
- **Rich amenities explorer:** Filter by categories (e.g. school, healthcare, market, green space)
- **Flat type filter:** Instantly sort results by flat type (3/4/5-room, executive, multi-generation, etc)
- **MRT exit mapping:** See all MRT exits—names, coordinates, and codes—using parsed Singapore government datasets
- **Community contribution:** Users can propose missing amenities, upvote submissions, and help expand the database

***

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/shrujann/MyHDBSense.git
cd MyHDBSense/amenities_tracker
```

### 2. Install Python requirements

**Make sure you have Python 3 and pip installed.**  
Create/activate a `virtualenv` (recommended), then install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Database setup

*If you need to migrate your database (Django models):*
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Run local development server

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in your browser.

***

## Code Structure

```
amenities_tracker/
├── accounts/                # User authentication, registration, flat tracker
├── amenities_tracker/       # Main Django app configuration & views
├── mappage/                 # Map pages, amenity explorer, and results views
├── db.sqlite3               # Local database (sample/demo data)
├── manage.py                # Django project runner
├── requirements.txt         # List of Python packages needed
```

- **Backend logic:** Python/Django views handle API calls (e.g., parsing KML/GeoJSON, running proximity searches, interacting with Singapore's APIs).
- **Frontend:** Uses Bootstrap, Leaflet.js, Bootstrap Icons for mobile-friendly maps and tables.
- **Data parsing:** Functions extract MRT info, flat listings, and amenities from external APIs (e.g., functions like `findmrt`, geocoding modules).
- **User experience:** Categories, filter chips, and modals for property details and contributions.

***

## Requirements

All Python dependencies are listed in [`requirements.txt`](amenities_tracker/requirements.txt).

This includes:
- Django, Flask (some features or APIs)
- requests, beautifulsoup4, geopy, pandas, etc.
- Bootstrap, Leaflet.js, Bootstrap Icons (included via CDN in HTML)

You can install all requirements in one line:

```bash
pip install -r requirements.txt
```

***

## Contributing

If you’d like to contribute:
- Fork the repo and submit a pull request
- File Issues or feature requests
- See [`amenities_tracker/accounts/`](amenities_tracker/accounts/) and [`amenities_tracker/mappage/`](amenities_tracker/mappage/) for main source code

***

## License, Contact & Credits

Project for NTU SC2006  
Original authors: [shrujann](https://github.com/shrujann), [ZachZYL](https://github.com/ZachZYL), [TomTang05](https://github.com/TomTang05), [MABSTAN](https://github.com/MABSTAN)

Reach us via GitHub Issues.

***

## Example Screenshots

*(To add: screenshots of map features, amenities explorer, property search page, etc.)*

***

## Project Status

Active development. Latest commits include:
- Improved data parsing for MRT and amenities
- Enhanced UI filter chips
- Bugfixes and database migrations

***

**Enjoy exploring Singapore housing smarter—with MyHDBSense!**
