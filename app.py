from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask import flash
import sqlite3
import os
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import joblib
import pandas as pd
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'bikeshare_secret_key_2024'

DB_PATH = os.path.join(os.path.dirname(__file__), 'bikeshare.db')

MODEL_PATH = os.path.join(os.path.dirname(__file__), "ml/demand_model.pkl")
demand_model = joblib.load(MODEL_PATH)

# ─────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'customer',
        email TEXT,
        contact TEXT,
        address TEXT,
        aadhar TEXT,
        pan TEXT,
        license TEXT,
        helmet TEXT DEFAULT 'no',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS base_stations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        locations TEXT,
        capacity INTEGER DEFAULT 100,
        available_bikes INTEGER DEFAULT 0,
        available_slots INTEGER DEFAULT 100
    );

    CREATE TABLE IF NOT EXISTS bikes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bike_no TEXT UNIQUE NOT NULL,
        model TEXT,
        year TEXT,
        description TEXT,
        station_id INTEGER,
        status TEXT DEFAULT 'available',
        FOREIGN KEY (station_id) REFERENCES base_stations(id)
    );

    CREATE TABLE IF NOT EXISTS rides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bike_id INTEGER,
        user_id INTEGER,
        source_station INTEGER,
        dest_station INTEGER,
        checkout_time TIMESTAMP,
        checkin_time TIMESTAMP,
        status TEXT DEFAULT 'active',
        success INTEGER DEFAULT 0,
        FOREIGN KEY (bike_id) REFERENCES bikes(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS no_service_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_id INTEGER,
        event_type TEXT,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed admin
    c.execute("SELECT id FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES ('admin','admin123','admin')")

    # Seed sample stations
    stations = [
        ('Ameerpet', 'Ameerpet, Hyderabad', 100, 8, 92),
        ('Secunderabad', 'Secunderabad, Hyderabad', 60, 5, 55),
        ('Nagole', 'Nagole, Hyderabad', 231, 12, 219),
        ('MGIT', 'Gandipet, Hyderabad', 105, 3, 102),
        ('Gandipet', 'Gandipet Road, Hyderabad', 100, 7, 93),
        ('Madhapura', 'Madhapura, Hyderabad', 120, 0, 120),
        ('Himayath Nagar', 'Himayath Nagar, Hyderabad', 120, 0, 120),
        ('CBIT', 'Gandipet, Hyderabad', 150, 0, 150),
        ('Dilshuknagar', 'Dilshuknagar, Hyderabad', 200, 9, 191),
    ]
    for s in stations:
        c.execute("INSERT OR IGNORE INTO base_stations (name, locations, capacity, available_bikes, available_slots) VALUES (?,?,?,?,?)", s)

    # Seed sample bikes
    bikes_data = [
        ('TS12378', 'Hero Splendor', '2021', 'Economy commuter', 1),
        ('TS12379', 'TVS Jupiter', '2022', 'Smooth city ride', 1),
        ('TS12380', 'Honda Activa', '2020', 'Popular scooter', 2),
        ('TS12381', 'Bajaj Pulsar', '2021', 'Sport commuter', 3),
        ('TS12382', 'Royal Enfield', '2019', 'Premium cruiser', 3),
        ('TS12383', 'Yamaha FZ', '2022', 'Stylish commuter', 4),
        ('TS12384', 'Suzuki Access', '2021', 'Comfortable scooter', 5),
        ('TS12385', 'Hero HF Deluxe', '2020', 'Budget bike', 9),
        ('TS12386', 'Honda CB Shine', '2022', 'Reliable commuter', 9),
        ('TS12387', 'TVS Apache', '2021', 'Performance bike', 5),
    ]
    for b in bikes_data:
        c.execute("INSERT OR IGNORE INTO bikes (bike_no, model, year, description, station_id) VALUES (?,?,?,?,?)", b)

    # Seed sample rides for analytics
    sample_rides = [
        (1, 1, 1, 2, '2024-01-15 08:30:00', '2024-01-15 09:00:00', 'completed', 1),
        (2, 1, 2, 1, '2024-01-16 09:00:00', '2024-01-16 09:45:00', 'completed', 1),
        (3, 2, 3, 4, '2024-01-17 10:00:00', '2024-01-17 10:30:00', 'completed', 1),
        (4, 4, 1, 3, '2024-01-18 11:00:00', '2024-01-18 11:45:00', 'completed', 1),
        (5, 5, 2, 5, '2024-01-19 14:00:00', '2024-01-19 14:30:00', 'completed', 1),
        (6, 1, 4, 2, '2024-01-20 07:30:00', '2024-01-20 08:00:00', 'completed', 1),
        (7, 3, 1, 5, '2024-01-21 16:00:00', '2024-01-21 16:30:00', 'completed', 0),
        (8, 2, 5, 1, '2024-01-22 08:00:00', '2024-01-22 08:30:00', 'completed', 1),
        (9, 6, 3, 2, '2024-01-23 09:30:00', '2024-01-23 10:00:00', 'completed', 1),
        (10, 7, 4, 3, '2024-01-24 11:30:00', '2024-01-24 12:00:00', 'completed', 1),
    ]
    for r in sample_rides:
        c.execute("INSERT OR IGNORE INTO rides (bike_id, user_id, source_station, dest_station, checkout_time, checkin_time, status, success) VALUES (?,?,?,?,?,?,?,?)", r)

    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# AUTH DECORATORS
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
# CHART HELPER
# ─────────────────────────────────────────────

def make_chart(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=130, facecolor='#0f1117')
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_b64

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        conn = get_db()
        try:
            conn.execute("""INSERT INTO users (username, password, email, contact, address, aadhar, pan, license, helmet)
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                (data['username'], data['password'], data.get('email'), data.get('contact'),
                 data.get('address'), data.get('aadhar'), data.get('pan'), data.get('license'), data.get('helmet','no')))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'danger')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    stations = conn.execute("SELECT * FROM base_stations").fetchall()
    total_bikes = conn.execute("SELECT COUNT(*) FROM bikes").fetchone()[0]
    active_rides = conn.execute("SELECT COUNT(*) FROM rides WHERE status='active'").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0]
    success_rate_row = conn.execute("SELECT ROUND(AVG(success)*100,1) FROM rides WHERE status='completed'").fetchone()
    success_rate = success_rate_row[0] if success_rate_row[0] else 0

    recent_rides = conn.execute("""
        SELECT r.*, u.username, bs.name as source_name, bd.name as dest_name
        FROM rides r
        JOIN users u ON r.user_id = u.id
        JOIN base_stations bs ON r.source_station = bs.id
        LEFT JOIN base_stations bd ON r.dest_station = bd.id
        ORDER BY r.id DESC LIMIT 5
    """).fetchall()
    conn.close()
    return render_template('dashboard.html', stations=stations, total_bikes=total_bikes,
                           active_rides=active_rides, total_users=total_users,
                           success_rate=success_rate, recent_rides=recent_rides)


@app.route('/stations')
@login_required
def stations():
    conn = get_db()

    query = request.args.get("q", "")
    if query:
        stations = conn.execute("""
            SELECT * FROM base_stations
            WHERE name LIKE ? OR locations LIKE ?
        """, (f"%{query}%", f"%{query}%")).fetchall()
    else:
        stations = [dict(row) for row in conn.execute("SELECT * FROM base_stations").fetchall()]

    # Prediction logic
    for s in stations:
        rows = conn.execute("""
            SELECT strftime('%H', checkout_time) as hour
            FROM rides
            WHERE source_station = ?
        """, (s["id"],)).fetchall()

        if not rows:
            s["demand"] = "Low"
            s["peak_hour"] = "-"
            continue

        hour_counts = {}
        for r in rows:
            h = int(r["hour"])
            hour_counts[h] = hour_counts.get(h, 0) + 1

        peak_hour = max(hour_counts, key=hour_counts.get)
        peak_count = hour_counts[peak_hour]
        score = min(100, peak_count * 10)

        if score > 70:
            level = "High"
        elif score > 40:
            level = "Moderate"
        else:
            level = "Low"

        s["demand"] = level
        s["peak_hour"] = peak_hour

    conn.close()
    return render_template("stations.html", stations=stations, query=query)

@app.route('/stations/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_station():
    if request.method == 'POST':
        name = request.form['name']
        locations = request.form['locations']
        capacity = int(request.form['capacity'])
        conn = get_db()
        try:
            conn.execute("INSERT INTO base_stations (name, locations, capacity, available_bikes, available_slots) VALUES (?,?,?,0,?)",
                         (name, locations, capacity, capacity))
            conn.commit()
            flash('Station added successfully!', 'success')
            return redirect(url_for('stations'))
        except sqlite3.IntegrityError:
            flash('Station name already exists.', 'danger')
        finally:
            conn.close()
    return render_template('add_station.html')

@app.route('/bikes')
@login_required
def bikes():
    conn = get_db()
    rows = conn.execute("""SELECT b.*, bs.name as station_name FROM bikes b
                           LEFT JOIN base_stations bs ON b.station_id = bs.id""").fetchall()
    conn.close()
    return render_template('bikes.html', bikes=rows)

@app.route('/bikes/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_bike():
    conn = get_db()
    stations = conn.execute("SELECT * FROM base_stations").fetchall()
    if request.method == 'POST':
        bike_no = request.form['bike_no']
        model = request.form['model']
        year = request.form['year']
        description = request.form['description']
        station_id = int(request.form['station_id'])
        try:
            conn.execute("INSERT INTO bikes (bike_no, model, year, description, station_id) VALUES (?,?,?,?,?)",
                         (bike_no, model, year, description, station_id))
            conn.execute("UPDATE base_stations SET available_bikes = available_bikes + 1, available_slots = available_slots - 1 WHERE id=?", (station_id,))
            conn.commit()
            flash('Bike registered successfully!', 'success')
            return redirect(url_for('bikes'))
        except sqlite3.IntegrityError:
            flash('Bike number already exists.', 'danger')
        finally:
            conn.close()
        return render_template('add_bike.html', stations=stations)
    conn.close()
    return render_template('add_bike.html', stations=stations)

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    conn = get_db()
    stations = conn.execute("SELECT * FROM base_stations WHERE available_bikes > 0").fetchall()
    if request.method == 'POST':
        station_id = int(request.form['station_id'])
        bike = conn.execute("SELECT * FROM bikes WHERE station_id=? AND status='available' LIMIT 1", (station_id,)).fetchone()
        if not bike:
            flash('No bikes available at this station.', 'warning')
        else:
            conn.execute("INSERT INTO rides (bike_id, user_id, source_station, checkout_time, status) VALUES (?,?,?,?,?)",
                         (bike['id'], session['user_id'], station_id, datetime.now(), 'active'))
            conn.execute("UPDATE bikes SET status='rented' WHERE id=?", (bike['id'],))
            conn.execute("UPDATE base_stations SET available_bikes = available_bikes - 1 WHERE id=?", (station_id,))
            conn.commit()
            flash(f'Bike {bike["bike_no"]} checked out successfully!', 'success')
            conn.close()
            return redirect(url_for('my_rides'))
    conn.close()
    return render_template('checkout.html', stations=stations)

@app.route('/checkin', methods=['GET', 'POST'])
@login_required
def checkin():
    conn = get_db()
    active_ride = conn.execute("""SELECT r.*, b.bike_no, bs.name as source_name
                                  FROM rides r JOIN bikes b ON r.bike_id=b.id
                                  JOIN base_stations bs ON r.source_station=bs.id
                                  WHERE r.user_id=? AND r.status='active'""",
                               (session['user_id'],)).fetchone()
    stations = conn.execute("SELECT * FROM base_stations").fetchall()

    if request.method == 'POST' and active_ride:
        dest_station_id = int(request.form['station_id'])
        dest_station = conn.execute("SELECT * FROM base_stations WHERE id=?", (dest_station_id,)).fetchone()
        success = 1 if dest_station['available_slots'] > 0 else 0

        conn.execute("""UPDATE rides SET dest_station=?, checkin_time=?, status='completed', success=?
                        WHERE id=?""", (dest_station_id, datetime.now(), success, active_ride['id']))
        conn.execute("UPDATE bikes SET status='available', station_id=? WHERE id=?",
                     (dest_station_id, active_ride['bike_id']))
        conn.execute("UPDATE base_stations SET available_bikes = available_bikes + 1 WHERE id=?", (dest_station_id,))
        conn.commit()
        flash('Bike returned successfully!', 'success')
        conn.close()
        return redirect(url_for('my_rides'))
    conn.close()
    return render_template('checkin.html', active_ride=active_ride, stations=stations)

@app.route('/my_rides')
@login_required
def my_rides():
    conn = get_db()
    rides = conn.execute("""SELECT r.*, b.bike_no, b.model, bs.name as source_name, bd.name as dest_name
                            FROM rides r JOIN bikes b ON r.bike_id=b.id
                            JOIN base_stations bs ON r.source_station=bs.id
                            LEFT JOIN base_stations bd ON r.dest_station=bd.id
                            WHERE r.user_id=? ORDER BY r.id DESC""",
                         (session['user_id'],)).fetchall()
    conn.close()
    return render_template('my_rides.html', rides=rides)


@app.route('/trip_advisor')
@login_required
def trip_advisor():
    conn = get_db()

    # Ride stats + station data
    data = conn.execute("""
        SELECT bs.id, bs.name, bs.available_bikes, bs.available_slots, bs.capacity,
               COUNT(r.id) as ride_count,
               SUM(CASE WHEN r.success = 1 THEN 1 ELSE 0 END) as success_count
        FROM base_stations bs
        LEFT JOIN rides r ON bs.id = r.source_station
        GROUP BY bs.id
    """).fetchall()

    max_rides = max((row['ride_count'] for row in data), default=1) or 1
    recommendations = []

    for row in data:
        # ML Demand Prediction
        now = datetime.now()
        hour = now.hour
        pred = demand_model.predict([[row['id'], hour]])
        predicted_rides = round(pred[0], 2)

        if predicted_rides > 15:
            demand_level = "High"
        elif predicted_rides > 7:
            demand_level = "Moderate"
        else:
            demand_level = "Low"
    
        # Activeness
        activeness = (row['ride_count'] / max_rides) if max_rides else 0

        # Availability
        availability = (row['available_bikes'] / row['capacity']) if row['capacity'] else 0

        # Success rate
        success_rate = (row['success_count'] / row['ride_count']) if row['ride_count'] else 0

        # Slot balance
        slot_balance = (row['available_slots'] / row['capacity']) if row['capacity'] else 0

        # Final score
        trip_score = round(
            (availability * 0.30 +
             activeness * 0.25 +
             success_rate * 0.25 +
             slot_balance * 0.20) * 100, 1
        )

        recommendations.append({
            'id': row['id'],
            'name': row['name'],
            'available_bikes': row['available_bikes'],
            'available_slots': row['available_slots'],
            'capacity': row['capacity'],
            'activeness': round(activeness * 100, 1),
            'availability_score': round(availability * 100, 1),
            'success_rate': round(success_rate * 100, 1),
            'slot_balance': round(slot_balance * 100, 1),
            'trip_score': trip_score,
            'recommendation':
                "Highly Recommended" if trip_score >= 70 else
                "Recommended" if trip_score >= 45 else
                "Low Priority",
            'predicted_rides': predicted_rides,
            'demand_level': demand_level
        })

    recommendations.sort(key=lambda x: x['trip_score'], reverse=True)
    conn.close()

    return render_template('trip_advisor.html', recommendations=recommendations)
@app.route('/analytics')
@login_required
@admin_required
def analytics():
    conn = get_db()

    # 1. Bike usage by station (bar chart)
    usage_data = conn.execute("""
        SELECT bs.name, COUNT(r.id) as ride_count
        FROM base_stations bs LEFT JOIN rides r ON bs.id = r.source_station
        GROUP BY bs.id ORDER BY ride_count DESC LIMIT 8
    """).fetchall()

    fig1, ax1 = plt.subplots(figsize=(8, 4))
    fig1.patch.set_facecolor('#0f1117')
    ax1.set_facecolor('#1a1d2e')
    names = [r['name'] for r in usage_data]
    counts = [r['ride_count'] for r in usage_data]
    bars = ax1.bar(names, counts, color=['#00d4aa' if c == max(counts) else '#3a7bd5' for c in counts], edgecolor='none', width=0.6)
    ax1.set_title('Ride Frequency by Station', color='white', fontsize=13, pad=12)
    ax1.set_xlabel('Station', color='#aaa', fontsize=9)
    ax1.set_ylabel('Total Rides', color='#aaa', fontsize=9)
    ax1.tick_params(colors='#ccc', labelsize=7)
    ax1.spines[:].set_color('#333')
    plt.xticks(rotation=30, ha='right')
    chart1 = make_chart(fig1)

    # 2. Success rate pie chart
    success_data = conn.execute("""SELECT success, COUNT(*) as cnt FROM rides WHERE status='completed' GROUP BY success""").fetchall()
    fig2, ax2 = plt.subplots(figsize=(5, 4))
    fig2.patch.set_facecolor('#0f1117')
    ax2.set_facecolor('#0f1117')
    s_map = {r['success']: r['cnt'] for r in success_data}
    vals = [s_map.get(1, 0), s_map.get(0, 0)]
    labels = ['Successful', 'Unsuccessful']
    colors = ['#00d4aa', '#e74c3c']
    wedges, texts, autotexts = ax2.pie(vals, labels=labels, colors=colors, autopct='%1.1f%%',
                                        startangle=140, textprops={'color': 'white', 'fontsize': 9},
                                        wedgeprops={'edgecolor': '#0f1117', 'linewidth': 2})
    for at in autotexts:
        at.set_color('white')
    ax2.set_title('Rental Success Rate', color='white', fontsize=13, pad=12)
    chart2 = make_chart(fig2)

    # 3. Station capacity vs availability
    cap_data = conn.execute("SELECT name, capacity, available_bikes FROM base_stations ORDER BY capacity DESC LIMIT 8").fetchall()
    fig3, ax3 = plt.subplots(figsize=(8, 4))
    fig3.patch.set_facecolor('#0f1117')
    ax3.set_facecolor('#1a1d2e')
    x = range(len(cap_data))
    ax3.bar(x, [r['capacity'] for r in cap_data], color='#3a7bd5', alpha=0.5, label='Capacity', width=0.4)
    ax3.bar([i+0.4 for i in x], [r['available_bikes'] for r in cap_data], color='#00d4aa', alpha=0.9, label='Available', width=0.4)
    ax3.set_xticks([i+0.2 for i in x])
    ax3.set_xticklabels([r['name'] for r in cap_data], rotation=30, ha='right', color='#ccc', fontsize=7)
    ax3.set_title('Station Capacity vs Available Bikes', color='white', fontsize=13, pad=12)
    ax3.set_ylabel('Bikes', color='#aaa', fontsize=9)
    ax3.tick_params(colors='#ccc', labelsize=8)
    ax3.spines[:].set_color('#333')
    ax3.legend(facecolor='#1a1d2e', labelcolor='white', fontsize=9)
    chart3 = make_chart(fig3)

    # Stats
    total_rides = conn.execute("SELECT COUNT(*) FROM rides").fetchone()[0]
    success_pct = conn.execute("SELECT ROUND(AVG(success)*100,1) FROM rides WHERE status='completed'").fetchone()[0] or 0
    freq_users = conn.execute("""SELECT u.username, COUNT(r.id) as cnt FROM rides r
                                 JOIN users u ON r.user_id=u.id GROUP BY r.user_id ORDER BY cnt DESC LIMIT 5""").fetchall()
    bike_history = conn.execute("""SELECT b.bike_no, b.model, bs.name as source, bd.name as dest, COUNT(r.id) as cnt
                                   FROM rides r JOIN bikes b ON r.bike_id=b.id
                                   JOIN base_stations bs ON r.source_station=bs.id
                                   LEFT JOIN base_stations bd ON r.dest_station=bd.id
                                   WHERE r.dest_station IS NOT NULL
                                   GROUP BY r.source_station, r.dest_station
                                   ORDER BY cnt DESC LIMIT 8""").fetchall()
    conn.close()
    return render_template('analytics.html', chart1=chart1, chart2=chart2, chart3=chart3,
                           total_rides=total_rides, success_pct=success_pct,
                           freq_users=freq_users, bike_history=bike_history)

@app.route('/users')
@login_required
@admin_required
def manage_users():
    conn = get_db()
    users = conn.execute("SELECT * FROM users WHERE role='customer' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('users.html', users=users)

# ─── API routes for Supabase migration readiness ───
@app.route('/api/stations')
def api_stations():
    conn = get_db()
    stations = [dict(row) for row in conn.execute("SELECT * FROM base_stations").fetchall()]
    conn.close()
    return jsonify(stations)

@app.route('/api/bikes')
def api_bikes():
    conn = get_db()
    bikes = [dict(row) for row in conn.execute("""SELECT b.*, bs.name as station_name
              FROM bikes b LEFT JOIN base_stations bs ON b.station_id=bs.id""").fetchall()]
    conn.close()
    return jsonify(bikes)

@app.route('/api/rides')
def api_rides():
    conn = get_db()
    rides = [dict(row) for row in conn.execute("SELECT * FROM rides ORDER BY id DESC LIMIT 50").fetchall()]
    conn.close()
    return jsonify(rides)

@app.route("/predict_demand/<int:station_id>")
@login_required
def predict_demand(station_id):

    now = datetime.now()
    hour = (now.hour+1) % 24

    prediction = demand_model.predict([[station_id, hour]])
    predicted_rides = prediction[0]

    if predicted_rides > 15:
        level = "High Demand"
    elif predicted_rides > 7:
        level = "Moderate Demand"
    else:
        level = "Low Demand"

    return jsonify({
        "station_id": station_id,
        "hour": hour,
        "predicted_rides": round(predicted_rides, 2),
        "prediction": level
    })
    
@app.route("/best_station")
@login_required
def best_station():
    conn = get_db()

    stations = [dict(row) for row in conn.execute("SELECT * FROM base_stations").fetchall()]

    best = None
    best_score = -1

    for s in stations:
        availability = s["available_bikes"] / s["capacity"] if s["capacity"] else 0

        rides = conn.execute("""
            SELECT COUNT(*) as c FROM rides
            WHERE source_station = ?
        """, (s["id"],)).fetchone()["c"]

        demand_penalty = min(1, rides / 50)

        score = availability - demand_penalty

        if score > best_score:
            best_score = score
            best = s

    conn.close()

    return jsonify({
        "best_station": best["name"],
        "available_bikes": best["available_bikes"],
        "score": round(best_score, 2),
        "reason": "Best availability with lowest demand"
    })
    
@app.route("/cancel_ride/<int:ride_id>")
@login_required
def cancel_ride(ride_id):
    conn = get_db()

    ride = conn.execute("SELECT * FROM rides WHERE id=? AND user_id=?", (ride_id,session["user_id"])).fetchone()

    if not ride or ride["status"] != "active":
        conn.close()
        from flask import flash
        flash("Ride cancelled successfully.", "success")
        flash("Ride cancelled successfully.", "success")
        return redirect(url_for("my_rides"))

    # update ride
    conn.execute("UPDATE rides SET status='cancelled' WHERE id=?", (ride_id,))

    # release bike
    conn.execute("UPDATE bikes SET status='available' WHERE id=?", (ride["bike_id"],))

    # update station counts
    conn.execute("""
        UPDATE base_stations
        SET available_bikes = available_bikes + 1,
            available_slots = available_slots + 1
        WHERE id = ?
    """, (ride["source_station"],))

    conn.commit()
    conn.close()

    return redirect(url_for("my_rides"))
    

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
