# 🚲 BikeShare — Utilization-Aware Trip Advisor

A full-featured bike-sharing trip advisor app built with Python + Flask + SQLite + Bootstrap.

## Project Structure

```
bikeshare/
├── app.py                  # Main Flask application (all routes + logic)
├── requirements.txt
├── bikeshare.db            # Auto-created SQLite database (gitignore this)
├── templates/
│   ├── base.html           # Sidebar layout shell
│   ├── index.html          # Public landing page
│   ├── login.html          # Login page
│   ├── register.html       # Registration page
│   ├── dashboard.html      # Main dashboard
│   ├── stations.html       # Station listing
│   ├── bikes.html          # Bike fleet view
│   ├── trip_advisor.html   # Core trip advisor
│   ├── analytics.html      # Charts + reports (admin)
│   ├── checkout.html       # Rent a bike
│   ├── checkin.html        # Return a bike
│   ├── my_rides.html       # Ride history
│   ├── add_station.html    # Admin: add station
│   ├── add_bike.html       # Admin: register bike
│   └── users.html          # Admin: user list
└── static/                 # (for any custom CSS/JS/images)
```

## Quick Start

```bash
# 1. Install dependencies
pip install flask matplotlib

# 2. Run the app
python app.py

# 3. Open browser
http://localhost:5000

# Demo login
Username: admin
Password: admin123
```

## Features

| Feature | Description |
|---------|-------------|
| 🗺️ Trip Advisor | Ranks stations by trip score (availability + activeness) |
| 📊 Analytics | Matplotlib charts: ride frequency, success rate, capacity |
| 🚲 Bike Fleet | Register and track bikes across stations |
| 🔁 Checkout/Checkin | Full bike rental & return flow |
| 👥 User Management | Admin panel for registered users |
| 🔐 Auth | Session-based login with admin/customer roles |
| 🌐 REST API | `/api/stations`, `/api/bikes`, `/api/rides` — Supabase-ready |

## Supabase Migration

The app is structured for easy Supabase swap:

1. Replace `get_db()` with `supabase.table(...)` calls
2. All DB queries are in `app.py` — no scattered ORM magic
3. REST API endpoints (`/api/*`) already mirror Supabase response format
4. `session['user_id']` maps cleanly to Supabase auth UID

## Trip Score Formula

```
trip_score = (activeness × 0.4) + (availability_score × 0.6)

where:
  activeness = (station_rides / max_rides_any_station) × 100
  availability_score = (available_bikes / capacity) × 100
```

Score > 60 → Highly Recommended  
Score 30–60 → Moderate  
Score < 30 → Low Activity
