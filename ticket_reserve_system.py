from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from mysql.connector import Error
import uuid
from functools import wraps
import hashlib
from datetime import datetime, timedelta

def is_agent_logged_in():
    return 'username' in session and session.get('role') == 'agent'
def agent_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_agent_logged_in():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def is_staff_logged_in():
    return 'username' in session and session.get('role') == 'staff'

def staff_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_staff_logged_in():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def refresh_staff_permissions(username):
    """
    Load the permission list for a staff user into session['permissions'].
    Call this after login or whenever permissions change.
    """
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("SELECT permission_type FROM Permission_status WHERE staff_email=%s", (username,))
    session['permissions'] = [row[0] for row in cur.fetchall()]
    cur.close(); conn.close()

def permission_required(*allowed):
    """
    Decorator:  ensure logged‑in staff member has at least one of the
    given permissions.  If not, return 403.
    """
    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            if not is_staff_logged_in():
                return redirect(url_for('login'))
            perms = session.get('permissions', [])
            if not any(p in perms for p in allowed):
                return "Unauthorized – missing permission", 403
            return f(*args, **kwargs)
        return inner
    return decorator

app = Flask(__name__)
app.secret_key = '12345678' 
db_config = {
    'host': 'localhost',
    'user': 'admin',       
    'password': '12345678',
    'database': 'ticket_reserve_system'
}


def get_db():
    conn = mysql.connector.connect(**db_config)
    return conn

def is_customer_logged_in():
    return 'username' in session and 'role' in session and session['role'] == 'customer'

def get_db_connection():
    """
    Creates and returns a connection to the MySQL database.
    """
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
    return None

@app.route('/')
def index():
    """
    Home page logic:
    - If a user is logged in (session contains 'username'), redirect to the home page.
    - Otherwise, render the index (landing) page.
    """
    if 'username' in session:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/home')
def home():
    """
    A sample home page to be shown after successful login.
    """
    return render_template('login.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')  
        password = request.form.get('password')
        
        connection = get_db_connection()
        if connection is None:
            error = "Error connecting to the database."
            return render_template('login.html', error=error)
        
        found_user = None
        found_role = None
        
        try:
            cursor = connection.cursor(dictionary=True)
            query = "SELECT email, name_customer FROM Customer WHERE email = %s AND customer_password = MD5(%s)"
            cursor.execute(query, (username, password))
            user = cursor.fetchone()
            if user:
                found_user = user
                found_role = "customer"
            else:
                
                query = "SELECT email, Name_agent FROM Booking_agent WHERE email = %s AND agent_password = MD5(%s)"
                cursor.execute(query, (username, password))
                user = cursor.fetchone()
                if user:
                    found_user = user
                    found_role = "agent"
                else:
                    
                    query = "SELECT staff_email, username FROM Airline_staff WHERE staff_email = %s AND password_stuff = Md5(%s)"
                    cursor.execute(query, (username, password))
                    user = cursor.fetchone()
                    if user:
                        found_user = user
                        found_role = "staff"
                        refresh_staff_permissions(username)
            
            cursor.close()
            connection.close()
            
            if found_user:
        
                session['username'] = username
                session['role'] = found_role

                
                if found_role == "customer":
                    return redirect(url_for('customer_home'))
                elif found_role == "agent":
                    return redirect(url_for('agent_home'))
                elif found_role == "staff":
                    
                    return redirect(url_for('staff_home'))
                else:
                    
                    return redirect(url_for('home'))
            else:
                error = "Invalid username or password. Please try again."
        except Error as e:
            error = f"An error occurred: {e}"
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        role = request.form.get('role')
        connection = get_db_connection()
        if connection is None:
            error = "Error connecting to the database."
            return render_template('register.html', error=error)
        
        try:
            cursor = connection.cursor()
            if role == 'customer':
                # Retrieve Customer fields
                email = request.form.get('email_customer')
                password = request.form.get('password_customer')
                name_customer = request.form.get('name_customer')
                phone_number = request.form.get('phone_number')
                passport_number = request.form.get('passport_number')
                
                query = """
                  INSERT INTO Customer (email, customer_password, name_customer, phone_number, passport_number)
                  VALUES (%s, MD5(%s), %s, %s, %s)
                """
                cursor.execute(query, (email, password, name_customer, phone_number, passport_number))
            
            elif role == 'agent':
                # Retrieve Booking Agent fields
                email      = request.form['email_agent']
                agent_name = request.form['agent_name']
                password   = request.form['password_agent']
            
                try:
                    # Begin a transaction
                    connection.start_transaction()

                    # 1) Lock the table and fetch the current max ID
                    cursor.execute("""
                        SELECT MAX(booking_agent_id) AS max_id
                        FROM Booking_agent
                        FOR UPDATE
                    """)
                    row = cursor.fetchone()
                    next_id = (row[0] or 0) + 1

                    # 2) Insert the new agent with that ID
                    cursor.execute("""
                        INSERT INTO Booking_agent
                        (email, Name_agent, agent_password, booking_agent_id)
                        VALUES (%s, %s, MD5(%s), %s)
                    """, (email, agent_name, password, next_id))

                    # 3) Commit once both statements succeed
                    connection.commit()

                except Error as e:
                    # Roll back on any error
                    connection.rollback()
                    error = f"An error occurred during agent registration: {e}"
                    cursor.close()
                    connection.close()
                    return render_template('register.html', error=error)

                cursor.close()
                connection.close()
                return redirect(url_for('login'))
            
            elif role == 'staff':
                #More On this later
                # Retrieve Airline Staff fields
                email = request.form.get('email_staff')
                username = request.form.get('username_staff')
                password = request.form.get('password_staff')
                airline_name = request.form.get('airline_name')
                dob = request.form.get('dob_staff')  # Date should be in 'YYYY-MM-DD'
                first_name = request.form.get('first_name')
                last_name = request.form.get('last_name')
                
                query = """
                  INSERT INTO Airline_staff (username, password_stuff, airline_name, date_of_birth, first_name, last_name, staff_email)
                  VALUES (%s, MD5(%s), %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (username, password, airline_name, dob, first_name, last_name, email))
            
            else:
                error = "Invalid registration type selected."
                return render_template('register.html', error=error)
            
            connection.commit()
            cursor.close()
            connection.close()
            # Redirect to login page after successful registration.
            return redirect(url_for('login'))
        except Error as e:
            connection.rollback()
            error = f"An error occurred during registration: {e}"
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/customer/home')
def customer_home():
    if not is_customer_logged_in():
        return redirect(url_for('login'))
    return render_template('customer_home.html')


@app.route('/customer/search_and_purchase', methods=['GET', 'POST'])
def customer_search_and_purchase():
    if not is_customer_logged_in():
        return redirect(url_for('login'))
    
    purchase_success = False
    ticket_id       = None
    error           = None
    search_results  = None

    # 1) Handle purchase
    if request.method == 'POST':
        flight_id = request.form.get('flight_id')
        if not flight_id:
            error = "No flight selected."
        else:
            conn   = get_db()
            cursor = conn.cursor(dictionary=True)

            conn.start_transaction()
            # a) Fetch flight + airplane_id
            cursor.execute("""
                SELECT airline_name,
                       flight_number,
                       departure_airport,
                       arrival_airport,
                       departure_time,
                       arrival_time,
                       price,
                       airplane_id
                  FROM Flight
                 WHERE flight_number = %s
            """, (flight_id,))
            flight = cursor.fetchone()

            if not flight:
                error = "Flight not found."
            else:
                # b) Count sold tickets
                cursor.execute("""
                    SELECT COUNT(*) AS sold_count
                      FROM Ticket
                     WHERE airline_name = %s
                       AND flight_number = %s
                """, (flight['airline_name'], flight['flight_number']))
                sold_count = cursor.fetchone()['sold_count'] or 0

                # c) Lookup plane capacity
                cursor.execute("""
                    SELECT seats
                      FROM Airplane
                     WHERE airline_name = %s
                       AND airplane_id = %s
                """, (flight['airline_name'], flight['airplane_id']))
                row = cursor.fetchone()
                capacity = row['seats'] if row else 0

                # d) Validate capacity
                if sold_count >= capacity:
                    error = "Sorry, this flight is fully booked."
                    conn.rollback()
                else:
                    try:
                        # e) Create the ticket
                        ticket_uuid = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO Ticket
                              (ticket_id, airline_name, flight_number, customer_email)
                            VALUES (%s, %s, %s, %s)
                        """, (
                            ticket_uuid,
                            flight['airline_name'],
                            flight['flight_number'],
                            session['username']
                        ))
                        # Record the purchase
                        cursor.execute("""
                            INSERT INTO purchases
                              (ticket_id, customer_email, booking_agent_id, purchase_time)
                            VALUES (%s, %s, NULL, NOW())
                        """, (ticket_uuid, session['username']))
                        conn.commit()
                        purchase_success = True
                        ticket_id = ticket_uuid
                    except Error as e:
                        conn.rollback()
                        error = f"Error purchasing ticket: {e}"

            cursor.close()
            conn.close()

    # 2) Handle search (GET or after POST)
    source      = request.args.get('source_city_or_airport')
    destination = request.args.get('destination_city_or_airport')
    date        = request.args.get('date')

    if source or destination or date:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT flight_number, airline_name, departure_airport, arrival_airport,
                   departure_time, arrival_time, price, flight_number AS flight_id
              FROM Flight
             WHERE departure_time > NOW()
        """
        filters = []
        if source:
            query += """ AND (
                departure_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s)
                OR departure_airport LIKE %s)"""
            filters += [f"%{source}%", f"%{source}%"]
        if destination:
            query += """ AND (
                arrival_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s)
                OR arrival_airport LIKE %s)"""
            filters += [f"%{destination}%", f"%{destination}%"]
        if date:
            query += " AND DATE(departure_time) = %s"
            filters.append(date)

        cursor.execute(query, filters)
        search_results = cursor.fetchall()
        cursor.close()
        conn.close()

    # 3) Render combined search & purchase page
    return render_template(
        'customer_search_and_purchase.html',
        search_results=search_results,
        purchase_success=purchase_success,
        ticket_id=ticket_id,
        error=error
    )

@app.route('/public/flights', methods=['GET'])
def public_flights():
    """
    Public page for displaying all upcoming flights and allowing users
    to check flight status by flight_number, departure date, and/or arrival date.
    """
    # Retrieve search parameters from query string (if provided)
    flight_number = request.args.get('flight_number')
    departure_date = request.args.get('departure_date')
    arrival_date = request.args.get('arrival_date')
    
    conn = get_db()  # Using your function to get a database connection
    cursor = conn.cursor(dictionary=True)

    # Base query: upcoming flights (departure_time > now)
    query = """
        SELECT flight_number, airline_name, departure_airport, arrival_airport, 
               departure_time, arrival_time
        FROM Flight
        WHERE departure_time > NOW()
    """
    filters = []
    
    # Append additional conditions if search parameters are provided.
    if flight_number:
        query += " AND flight_number = %s "
        filters.append(flight_number)
    if departure_date:
        query += " AND DATE(departure_time) = %s "
        filters.append(departure_date)
    if arrival_date:
        query += " AND DATE(arrival_time) = %s "
        filters.append(arrival_date)
    
    query += " ORDER BY departure_time ASC"

    cursor.execute(query, filters)
    flights = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("public_flights.html", flights=flights)

@app.route('/public/search_flights', methods=['GET'])
def public_search_flights():
    source      = request.args.get('source_city_or_airport')
    destination = request.args.get('destination_city_or_airport')
    date        = request.args.get('date')

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT flight_number, airline_name, departure_airport, arrival_airport,
               departure_time, arrival_time
        FROM Flight
        WHERE departure_time > NOW()
    """
    filters = []
    if source:
        query += """ AND (
            departure_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s)
            OR departure_airport LIKE %s)"""
        filters += [f"%{source}%", f"%{source}%"]
    if destination:
        query += """ AND (
            arrival_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s)
            OR arrival_airport LIKE %s)"""
        filters += [f"%{destination}%", f"%{destination}%"]
    if date:
        query += " AND DATE(departure_time) = %s"
        filters.append(date)

    cursor.execute(query, filters)
    search_results = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('public_search_flights.html',
                           search_results=search_results)


# Public: Check a single flight’s status by flight number + dates
@app.route('/public/check_status', methods=['GET'])
def public_check_status():
    flight_number  = request.args.get('flight_number')
    departure_date = request.args.get('departure_date')
    arrival_date   = request.args.get('arrival_date')

    conn   = get_db()
    cursor = conn.cursor(buffered=True, dictionary=True)

    query = """
        SELECT flight_number, airline_name, departure_airport, arrival_airport,
               departure_time, arrival_time, flight_status
        FROM Flight
        WHERE 1=1
    """
    filters = []
    if flight_number:
        query += " AND flight_number = %s"
        filters.append(flight_number)
    if departure_date:
        query += " AND DATE(departure_time) = %s"
        filters.append(departure_date)
    if arrival_date:
        query += " AND DATE(arrival_time) = %s"
        filters.append(arrival_date)

    cursor.execute(query, filters)
    rows = cursor.fetchall()
    if not rows:
        flight = None  # No matching flight found
    else:
        flight = rows[0]
    cursor.close()
    conn.close()

    return render_template('public_check_status.html', flight=flight)

@app.route('/customer/upcoming_flights', methods=['GET'])
def customer_upcoming_flights():
    if not is_customer_logged_in():
        return redirect(url_for('login'))

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    source = request.args.get('source')
    destination = request.args.get('destination')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT F.flight_number, F.airline_name, F.departure_airport, F.arrival_airport, 
               F.departure_time, F.arrival_time
        FROM Flight F 
        JOIN Ticket T ON (T.airline_name = F.airline_name AND T.flight_number = F.flight_number)
        WHERE T.customer_email = %s 
          AND F.departure_time > NOW()
    """
    filters = [session['username']]

    if start_date:
        query += " AND DATE(F.departure_time) >= %s"
        filters.append(start_date)
    if end_date:
        query += " AND DATE(F.departure_time) <= %s"
        filters.append(end_date)
    if source:
        query += """
            AND (F.departure_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s)
                 OR F.departure_airport LIKE %s)
        """
        filters.append(f"%{source}%")
        filters.append(f"%{source}%")
    if destination:
        query += """
            AND (F.arrival_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s)
                 OR F.arrival_airport LIKE %s)
        """
        filters.append(f"%{destination}%")
        filters.append(f"%{destination}%")

    cursor.execute(query, filters)
    flights = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('customer_upcoming_flights.html', flights=flights)


@app.route('/customer/spending')
def customer_spending():
    if not is_customer_logged_in():
        return redirect(url_for('login'))

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT SUM(F.price) AS total_spent
        FROM Ticket T
        JOIN Flight F     ON T.airline_name = F.airline_name AND T.flight_number = F.flight_number
        JOIN Purchases P ON T.ticket_id = P.ticket_id
        WHERE T.customer_email = %s
    """
    filters = [session['username']]

    if start_date:
        query += " AND DATE(P.purchase_time) >= %s"
        filters.append(start_date)
    else:
        query += " AND P.purchase_time >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)"

    if end_date:
        query += " AND DATE(P.purchase_time) <= %s"
        filters.append(end_date)

    cursor.execute(query, filters)
    result = cursor.fetchone()
    total_spent = result['total_spent'] if result['total_spent'] else 0

    monthly_query   = """
       SELECT DATE_FORMAT(P.purchase_time, '%Y-%m') AS month_key,
               SUM(F.price)                 AS monthly_sum
        FROM Ticket T
        JOIN Flight F     ON T.airline_name = F.airline_name AND T.flight_number = F.flight_number
        JOIN Purchases P ON T.ticket_id = P.ticket_id
        WHERE T.customer_email = %s
    """
    m_filters = [session['username']]

    if start_date:
        monthly_query += " AND DATE(P.purchase_time) >= %s"
        m_filters.append(start_date)
    else:
        monthly_query += " AND P.purchase_time >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)"

    if end_date:
        monthly_query += " AND DATE(P.purchase_time) <= %s"
        m_filters.append(end_date)

    monthly_query += " GROUP BY month_key ORDER BY month_key"
    cursor.execute(monthly_query, m_filters)

    monthly_results = cursor.fetchall()
    cursor.close()
    conn.close()

    months = []
    monthly_spent = []
    for row in monthly_results:
        months.append(row['month_key'])
        monthly_spent.append(row['monthly_sum'])

    return render_template('customer_spending.html',
                           total_spent=total_spent,
                           months=months,
                           monthly_spent=monthly_spent)


###For agent
# ------------  AGENT HOME  ------------
@app.route('/agent/home')
@agent_required
def agent_home():
    return render_template('agent_home.html', title="Agent Home")

# ------------  SEARCH & PURCHASE  ------------
@app.route('/agent/search_and_purchase', methods=['GET', 'POST'])
@agent_required
def agent_search_and_purchase():
    """
    Agent may search flights (GET) and purchase for a customer (POST).
    Capacity + airline‑membership enforced.
    """
    purchase_success = False
    ticket_id        = None
    error            = None
    search_results   = None

    # ---------- PURCHASE ----------
    if request.method == 'POST':
        flight_id      = request.form.get('flight_id')
        customer_email = request.form.get('customer_email')

        if not flight_id or not customer_email:
            error = "Flight and customer email required."
        else:
            conn   = get_db()
            cursor = conn.cursor(dictionary=True)
            conn.start_transaction()
            # 1) fetch flight inc. airplane_id & airline
            cursor.execute("""
                SELECT airline_name, flight_number, airplane_id, price
                  FROM Flight
                 WHERE flight_number = %s
            """, (flight_id,))
            flight = cursor.fetchone()

            # 2) verify agent works for that airline
            cursor.execute("""
                SELECT 1
                  FROM Agent_status
                 WHERE agent_email = %s
                   AND airline_name = %s
            """, (session['username'], flight['airline_name'] if flight else None))
            allowed = cursor.fetchone() is not None

            if not flight:
                error = "Flight not found."
            elif not allowed:
                error = "You’re not authorized to sell tickets for that airline."
            else:
                # 3) capacity check
                cursor.execute("""
                    SELECT COUNT(*) AS sold
                      FROM Ticket
                     WHERE airline_name = %s
                       AND flight_number = %s
                """, (flight['airline_name'], flight['flight_number']))
                sold = cursor.fetchone()['sold']

                cursor.execute("""
                    SELECT seats
                      FROM Airplane
                     WHERE airline_name = %s
                       AND airplane_id  = %s
                """, (flight['airline_name'], flight['airplane_id']))
                capacity = cursor.fetchone()['seats']

                if sold >= capacity:
                    error = "Flight is fully booked."
                    conn.rollback()
                else:
                    try:
                        tid = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO Ticket
                              (ticket_id, airline_name, flight_number,
                               customer_email, booking_agent_id)
                            VALUES (%s, %s, %s, %s,
                               (SELECT booking_agent_id
                                  FROM Booking_agent
                                 WHERE email = %s))
                        """, (tid, flight['airline_name'], flight['flight_number'],
                              customer_email, session['username']))
                        # Add to purchases table (commission calculation later)
                        cursor.execute("""
                            INSERT INTO purchases
                              (ticket_id, customer_email, booking_agent_id, purchase_time)
                            VALUES (%s, %s,
                               (SELECT booking_agent_id FROM Booking_agent WHERE email=%s),
                               NOW())
                        """, (tid, customer_email, session['username']))
                        conn.commit()
                        purchase_success = True
                        ticket_id = tid
                    except Error as e:
                        conn.rollback()
                        error = f"Error: {e}"
            cursor.close()
            conn.close()

    # ---------- SEARCH ----------
    src  = request.args.get('source_city_or_airport')
    dest = request.args.get('destination_city_or_airport')
    date = request.args.get('date')
    if src or dest or date:
        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        q = """
            SELECT flight_number, airline_name, departure_airport, arrival_airport,
                   departure_time, arrival_time, price, flight_number AS flight_id
              FROM Flight
             WHERE departure_time > NOW()
        """
        params = []
        if src:
            q += """ AND (
                departure_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s)
                OR departure_airport LIKE %s)"""
            params += [f"%{src}%", f"%{src}%"]
        if dest:
            q += """ AND (
                arrival_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s)
                OR arrival_airport LIKE %s)"""
            params += [f"%{dest}%", f"%{dest}%"]
        if date:
            q += " AND DATE(departure_time) = %s"
            params.append(date)

        cursor.execute(q, params)
        search_results = cursor.fetchall()
        cursor.close()
        conn.close()

    return render_template('agent_search_and_purchase.html',
                           search_results=search_results,
                           purchase_success=purchase_success,
                           ticket_id=ticket_id,
                           error=error,
                           title="Agent Search & Purchase")

# ------------  VIEW MY FLIGHTS  ------------
@app.route('/agent/my_flights')
@agent_required
def agent_my_flights():
    start = request.args.get('start_date')
    end   = request.args.get('end_date')
    src   = request.args.get('source')
    dest  = request.args.get('destination')

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    q = """
        SELECT F.flight_number, F.airline_name, F.departure_airport,
               F.arrival_airport, F.departure_time, F.arrival_time
          FROM Flight F
          JOIN Ticket  T USING (airline_name, flight_number)
          JOIN Booking_agent BA ON T.booking_agent_id = BA.booking_agent_id
         WHERE BA.email = %s
           AND F.departure_time > NOW()
    """
    params = [session['username']]
    if start:
        q += " AND DATE(F.departure_time) >= %s"
        params.append(start)
    if end:
        q += " AND DATE(F.departure_time) <= %s"
        params.append(end)
    if src:
        q += " AND (F.departure_airport LIKE %s OR F.departure_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s))"
        params += [f"%{src}%", f"%{src}%"]
    if dest:
        q += " AND (F.arrival_airport LIKE %s OR F.arrival_airport IN (SELECT airport_name FROM Airport WHERE city LIKE %s))"
        params += [f"%{dest}%", f"%{dest}%"]

    cursor.execute(q, params)
    flights = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('agent_my_flights.html', flights=flights, title="Agent ‑ My Flights")

# ------------  COMMISSION DASHBOARD  ------------
@app.route('/agent/commission')
@agent_required
def agent_commission():
    start = request.args.get('start_date')
    end   = request.args.get('end_date')

    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    # Commission = 0.1 * price (assumption)
    q = """
        SELECT SUM(0.1*F.price) AS total_comm,
               COUNT(*)         AS tickets_sold,
               CASE WHEN COUNT(*)=0 THEN 0
                    ELSE SUM(0.1*F.price)/COUNT(*) END AS avg_comm
          FROM purchases   P
          JOIN Ticket      T USING(ticket_id)
          JOIN Flight      F USING(airline_name, flight_number)
          JOIN Booking_agent BA ON P.booking_agent_id = BA.booking_agent_id
         WHERE BA.email = %s
         AND P.purchase_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """
    params = [session['username']]
    if start or end:
        q = """
            SELECT SUM(0.1*F.price) AS total_comm,
                COUNT(*)         AS tickets_sold,
                CASE WHEN COUNT(*)=0 THEN 0
                        ELSE SUM(0.1*F.price)/COUNT(*) END AS avg_comm
            FROM purchases   P
            JOIN Ticket      T USING(ticket_id)
            JOIN Flight      F USING(airline_name, flight_number)
            JOIN Booking_agent BA ON P.booking_agent_id = BA.booking_agent_id
            WHERE BA.email = %s
        """
        if start:
            q += " AND DATE(P.purchase_time) >= %s"
            params.append(start)
        if end:
            q += " AND DATE(P.purchase_time) <= %s"
            params.append(end)

    cursor.execute(q, params)
    stats = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('agent_commission.html', stats=stats, title="Agent ‑ Commission")

# ------------  TOP CUSTOMERS  ------------
@app.route('/agent/top_customers')
@agent_required
def agent_top_customers():
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)

    # Top by tickets (6 months)
    cursor.execute("""
        SELECT
            t.customer_email,
            COUNT(*) AS num_tickets
        FROM Ticket t
        JOIN Booking_agent b 
            ON b.booking_agent_id = t.booking_agent_id
        JOIN purchases p
            ON p.ticket_id = t.ticket_id
        WHERE
            b.email = %s
            AND p.purchase_time >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY
            t.customer_email
        ORDER BY
            num_tickets DESC
        LIMIT 5;
    """, (session['username'],))
    top_tickets = cursor.fetchall()

    # Top by commission (1 year)
    cursor.execute("""
        SELECT
            p.customer_email,
            SUM(f.price * 0.10) AS total_commission
        FROM purchases p
        JOIN Ticket t
            ON p.ticket_id = t.ticket_id
        JOIN Flight f
            ON f.airline_name = t.airline_name
            AND f.flight_number = t.flight_number
        JOIN Booking_agent b
            ON b.booking_agent_id = p.booking_agent_id
        WHERE
            p.booking_agent_id IS NOT NULL
            AND p.purchase_time >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
            AND b.email = %s
        GROUP BY
            p.customer_email
        ORDER BY
            total_commission DESC
        LIMIT 5
    """, (session['username'],))
    top_commission = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('agent_top_customers.html',
                           top_tickets=top_tickets,
                           top_commission=top_commission,
                           title="Agent ‑ Top Customers")


# ── Airline Staff Routes ──────────────────────────────────────────────────────

@app.route('/staff')
@staff_required
def staff_home():
    """Simple landing page for Airline Staff."""
    return render_template('staff_home.html', title='Staff Home')


@app.route('/staff/my_flights', methods=['GET'])
@staff_required
def staff_my_flights():
    """
    Show upcoming (and optionally filtered) flights for the airline this staff works for.
    """
    username = session['username']
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    # find airline_name
    cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
    row = cur.fetchone()
    airline = row['airline_name']

    # filters
    start = request.args.get('start_date')
    end   = request.args.get('end_date')
    src   = request.args.get('source')
    dst   = request.args.get('destination')

    query = """
      SELECT flight_number, departure_airport, arrival_airport,
             departure_time, arrival_time, flight_status
      FROM Flight
      WHERE airline_name=%s
        AND departure_time BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 30 DAY)
    """
    params = [airline]

    if start or end or src or dst:
        query = """
        SELECT flight_number, departure_airport, arrival_airport,
                departure_time, arrival_time, flight_status
        FROM Flight
        WHERE airline_name=%s
        """

        if start:
            query += " AND departure_time >= %s"; params.append(start)
        if end:
            query += " AND departure_time <= %s"; params.append(end)
        if src:
            query += " AND departure_airport LIKE %s"; params.append(f"%{src}%")
        if dst:
            query += " AND arrival_airport LIKE %s"; params.append(f"%{dst}%")

    query += " ORDER BY departure_time"
    cur.execute(query, tuple(params))
    flights = cur.fetchall()

    cur.close(); conn.close()
    return render_template('staff_my_flights.html',
                           flights=flights,
                           title='My Flights')


@app.route('/staff/create_flight', methods=['GET','POST'])
@staff_required
@permission_required('Admin', 'Operator')
def staff_create_flight():
    """
    Form to create a new Flight. Requires Admin permission.
    """
    if request.method == 'POST':
        username = session['username']
        conn = get_db(); cur = conn.cursor()
        # fetch airline
        cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
        airline = cur.fetchone()[0]

        data = (
            airline,
            request.form['flight_number'],
            request.form['price'],
            request.form['flight_status'],
            request.form['departure_time'],
            request.form['arrival_time'],
            request.form['departure_airport'],
            request.form['arrival_airport'],
            request.form['airplane_id']
        )
        try:
            cur.execute("""
              INSERT INTO Flight
              (airline_name, flight_number, price, flight_status,
               departure_time, arrival_time,
               departure_airport, arrival_airport, airplane_id)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, data)
            conn.commit()
            success = f"Flight {data[1]} created."
        except Exception as e:
            conn.rollback()
            success = f"Error: {e}"
        cur.close(); conn.close()
        return render_template('staff_create_flight.html',
                               message=success,
                               title='Create Flight')

    return render_template('staff_create_flight.html', title='Create Flight')


@app.route('/staff/change_status', methods=['GET','POST'])
@staff_required
@permission_required('Admin','Operator')
def staff_change_status():
    """
    Change status (e.g. On Time→Delayed) of an existing flight. Requires Operator permission.
    """
    username = session['username']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
    airline = cur.fetchone()['airline_name']

    statuses = ['SCHEDULED', 'ON TIME', 'DELAYED', 'DEPARTED', 'IN AIR', 'ARRIVED', "CANCELLED",
                'BOARDING', 'LANDED'
            ]

    if request.method=='POST':
        cur2 = conn.cursor()
        new_status = request.form['flight_status']
        if new_status not in statuses:
            msg = f"Invalid status: {new_status}"
        try:
            cur2.execute("""
              UPDATE Flight
              SET flight_status=%s
              WHERE airline_name=%s AND flight_number=%s
            """, (
              new_status,
              airline,
              request.form['flight_number']
            ))
            conn.commit()
            msg = "Status updated."
        except Exception as e:
            conn.rollback()
            msg = f"Error: {e}"
        cur2.close()
    else:
        msg = None

    # Get all flights for dropdown
    cur.execute("""
      SELECT flight_number, flight_status
      FROM Flight
      WHERE airline_name=%s
      ORDER BY departure_time
    """, (airline,))
    flights = cur.fetchall()

    cur.close(); conn.close()
    return render_template("staff_change_status.html",
                           flights=flights,
                           statuses = statuses,
                           message=msg,
                           title='Change Status')


@app.route('/staff/add_airplane', methods=['GET','POST'])
@staff_required
@permission_required('Admin', 'Operator')
def staff_add_airplane():
    """
    Add a new Airplane for this airline. Requires Admin permission.
    """
    if request.method=='POST':
        username = session['username']
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
        airline = cur.fetchone()[0]

        try:
            cur.execute("""
              INSERT INTO Airplane (airplane_id, airline_name, seats)
              VALUES (%s, %s, %s)
            """, (
              request.form['airplane_id'],
              airline,
              request.form['seats']
            ))
            conn.commit()
            msg = "Airplane added."
        except Exception as e:
            conn.rollback()
            msg = f"Error: {e}"
        cur.close(); conn.close()
        return render_template('staff_add_airplane.html',
                               message=msg,
                               title='Add Airplane')

    return render_template('staff_add_airplane.html', title='Add Airplane')


@app.route('/staff/add_airport', methods=['GET','POST'])
@staff_required
@permission_required('Admin')
def staff_add_airport():
    """
    Add a new Airport to the system. Requires Admin permission.
    """
    if request.method=='POST':
        conn = get_db(); cur = conn.cursor()
        try:
            cur.execute("""
              INSERT INTO Airport (airport_name, city)
              VALUES (%s, %s)
            """, (
              request.form['airport_name'],
              request.form['city']
            ))
            conn.commit()
            msg = "Airport added."
        except Exception as e:
            conn.rollback()
            msg = f"Error: {e}"
        cur.close(); conn.close()
        return render_template('staff_add_airport.html',
                               message=msg,
                               title='Add Airport')

    return render_template('staff_add_airport.html', title='Add Airport')


@app.route('/staff/view_agents')
@staff_required
def staff_view_agents():
    """
    View top 5 booking agents by tickets (1 month, 1 year) and by commission (1 year).
    """
    username = session['username']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
    airline = cur.fetchone()['airline_name']
    #All agents
    cur.execute("""
        SELECT ba.email AS agent_email
            FROM Booking_agent ba
            JOIN Agent_status a ON ba.email = a.agent_email
            WHERE a.airline_name = %s
    """, (airline,))
    all_agents = cur.fetchall()
    # Top 5 by tickets in past month
    cur.execute("""
      SELECT ba.email AS agent_email,
             COUNT(*) AS tickets_sold
      FROM Ticket t
      JOIN purchases p ON t.ticket_id=p.ticket_id
      JOIN Booking_agent ba ON t.booking_agent_id=ba.booking_agent_id
      WHERE t.airline_name=%s AND p.purchase_time>=DATE_SUB(NOW(), INTERVAL 1 MONTH)
      GROUP BY ba.email
      ORDER BY tickets_sold DESC
      LIMIT 5
    """, (airline,))
    top_tickets = cur.fetchall()

    cur.execute("""
      SELECT ba.email AS agent_email,
             COUNT(*) AS tickets_sold
      FROM Ticket t
      JOIN purchases p ON t.ticket_id=p.ticket_id
      JOIN Booking_agent ba ON t.booking_agent_id=ba.booking_agent_id
      WHERE t.airline_name=%s AND p.purchase_time>=DATE_SUB(NOW(), INTERVAL 1 YEAR)
      GROUP BY ba.email
      ORDER BY tickets_sold DESC
      LIMIT 5
    """, (airline,))
    top_tickets_yearly = cur.fetchall()

    # Top 5 by commission in past year (assume 10% rate)
    cur.execute("""
      SELECT ba.email AS agent_email,
             SUM(f.price*0.1) AS total_commission
      FROM Ticket t
      JOIN purchases p ON t.ticket_id=p.ticket_id
      JOIN Booking_agent ba ON t.booking_agent_id=ba.booking_agent_id
      JOIN Flight f ON t.airline_name=f.airline_name AND t.flight_number=f.flight_number
      WHERE t.airline_name=%s AND p.purchase_time>=DATE_SUB(NOW(), INTERVAL 1 YEAR)
      GROUP BY ba.email
      ORDER BY total_commission DESC
      LIMIT 5
    """, (airline,))
    top_comm = cur.fetchall()

    cur.close(); conn.close()
    return render_template('staff_view_agents.html',
                           all_agents = all_agents,
                           top_tickets=top_tickets,
                           top_tickets_yearly=top_tickets_yearly,
                           top_comm=top_comm,
                           title='Top Booking Agents')


@app.route('/staff/frequent_customers', methods=['GET', 'POST'])
@staff_required
def staff_frequent_customers():
    """
    Show the most frequent customer in the last year, and all flights they've taken.
    Allow staff to select a customer and view their flights on the airline.
    """
    username = session['username']
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Fetch the airline the staff belongs to
    cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
    airline = cur.fetchone()['airline_name']

    # Fetch the top customer in the last year
    cur.execute("""
      SELECT p.customer_email, COUNT(*) AS freq
      FROM Ticket t
      JOIN purchases p ON t.ticket_id = p.ticket_id
      WHERE t.airline_name = %s
        AND p.purchase_time >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
      GROUP BY p.customer_email
      ORDER BY freq DESC
      LIMIT 1
    """, (airline,))
    top_customer = cur.fetchone()

    # Fetch all customers who have purchased tickets for this airline
    cur.execute("""
      SELECT DISTINCT p.customer_email
      FROM Ticket t
      JOIN purchases p ON t.ticket_id = p.ticket_id
      WHERE t.airline_name = %s
    """, (airline,))
    all_customers = cur.fetchall()

    # If a specific customer is selected, fetch their flights
    selected_customer = request.form.get('customer_email') if request.method == 'POST' else None
    flights = []
    if selected_customer:
        cur.execute("""
          SELECT f.flight_number, f.departure_time, f.arrival_time, f.departure_airport, f.arrival_airport
          FROM Ticket t
          JOIN purchases p ON t.ticket_id = p.ticket_id
          JOIN Flight f ON t.airline_name = f.airline_name
                     AND t.flight_number = f.flight_number
          WHERE t.airline_name = %s
            AND p.customer_email = %s
        """, (airline, selected_customer))
        flights = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'staff_frequent_customers.html',
        top_customer=top_customer,
        all_customers=all_customers,
        selected_customer=selected_customer,
        flights=flights,
        title='Frequent Customers'
    )


@app.route('/staff/view_reports', methods=['GET'])
@staff_required
def staff_view_reports():
    """
    Total tickets sold and month-wise counts over a date range, last year, or last month.
    """
    try:
        username = session['username']
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # Fetch the airline the staff belongs to
        cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
        airline = cur.fetchone()['airline_name']

        # Determine the date range
        start = request.args.get('start_date')
        end = request.args.get('end_date')
        report_type = request.args.get('report_type')  # 'last_year' or 'last_month'

        if report_type == 'last_year':
            start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            end = datetime.now().strftime('%Y-%m-%d')
        elif report_type == 'last_month':
            start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            end = datetime.now().strftime('%Y-%m-%d')

        # Total tickets sold
        cur.execute("""
          SELECT COUNT(*) AS total_sold
          FROM Ticket t
          JOIN purchases p ON t.ticket_id = p.ticket_id
          WHERE t.airline_name = %s
            AND p.purchase_time BETWEEN %s AND %s
        """, (airline, start, end))
        total = cur.fetchone()

        # Month-wise breakdown
        cur.execute("""
          SELECT MONTH(p.purchase_time) AS month, COUNT(*) AS tickets
          FROM Ticket t
          JOIN purchases p ON t.ticket_id = p.ticket_id
          WHERE t.airline_name = %s
            AND p.purchase_time BETWEEN %s AND %s
          GROUP BY MONTH(p.purchase_time)
          ORDER BY month
        """, (airline, start, end))
        breakdown = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            'staff_view_reports.html',
            total=total,
            breakdown=breakdown,
            start_date=start,
            end_date=end,
            report_type=report_type,
            title='Sales Reports'
        )
    except Exception as e:
        print("An error occurred:", e)
        return "An error occurred while processing your request.", 500


@app.route('/staff/compare_revenue')
@staff_required
def staff_compare_revenue():
    """
    Pie-chart data: direct vs indirect revenue in last month & last year.
    """
    username = session['username']
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
    airline = cur.fetchone()[0]

    # last month
    cur.execute("""
      SELECT
        SUM(f.price) 
      FROM Ticket t
      JOIN purchases p ON t.ticket_id=p.ticket_id
      JOIN Flight f ON t.airline_name=f.airline_name
                 AND t.flight_number=f.flight_number
      WHERE t.airline_name=%s
        AND t.booking_agent_id IS NULL
        AND p.purchase_time>=DATE_SUB(NOW(), INTERVAL 1 MONTH)
    """, (airline,))
    direct_month = cur.fetchone()[0] or 0

    cur.execute("""
      SELECT
        SUM(f.price) 
      FROM Ticket t
      JOIN purchases p ON t.ticket_id=p.ticket_id
      JOIN Flight f ON t.airline_name=f.airline_name
                 AND t.flight_number=f.flight_number
      WHERE t.airline_name=%s
        AND t.booking_agent_id IS NOT NULL
        AND p.purchase_time>=DATE_SUB(NOW(), INTERVAL 1 MONTH)
    """, (airline,))
    indirect_month = cur.fetchone()[0] or 0

    # last year (same pattern)…
    cur.execute("""
      SELECT SUM(f.price)
      FROM Ticket t
      JOIN purchases p ON t.ticket_id=p.ticket_id
      JOIN Flight f ON t.airline_name=f.airline_name
                 AND t.flight_number=f.flight_number
      WHERE t.airline_name=%s
        AND t.booking_agent_id IS NULL
        AND p.purchase_time>=DATE_SUB(NOW(), INTERVAL 1 YEAR)
    """, (airline,))
    direct_year = cur.fetchone()[0] or 0

    cur.execute("""
      SELECT SUM(f.price)
      FROM Ticket t
      JOIN purchases p ON t.ticket_id=p.ticket_id
      JOIN Flight f ON t.airline_name=f.airline_name
                 AND t.flight_number=f.flight_number
      WHERE t.airline_name=%s
        AND t.booking_agent_id IS NOT NULL
        AND p.purchase_time>=DATE_SUB(NOW(), INTERVAL 1 YEAR)
    """, (airline,))
    indirect_year = cur.fetchone()[0] or 0

    cur.close(); conn.close()
    return render_template('staff_compare_revenue.html',
                           dm=direct_month, im=indirect_month,
                           dy=direct_year, iy=indirect_year,
                           title='Revenue Comparison')


@app.route('/staff/top_destinations')
@staff_required
def staff_top_destinations():
    """
    Top 3 most popular destinations for last 3 months and last year.
    """
    username = session['username']
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
    airline = cur.fetchone()['airline_name']

    cur.execute("""
        SELECT f.arrival_airport   AS dest,
                COUNT(*)            AS cnt
        FROM Ticket t
        JOIN purchases p 
            ON t.ticket_id = p.ticket_id
        JOIN Flight f 
            ON t.airline_name = f.airline_name
        AND t.flight_number = f.flight_number
        WHERE t.airline_name = %s
            AND p.purchase_time >= DATE_SUB(NOW(), INTERVAL 3 MONTH)
        GROUP BY f.arrival_airport
        ORDER BY cnt DESC
        LIMIT 3
    """, (airline,))
    m3 = cur.fetchall()

    cur.execute("""
        SELECT f.arrival_airport   AS dest,
                COUNT(*)            AS cnt
        FROM Ticket t
        JOIN purchases p 
            ON t.ticket_id = p.ticket_id
        JOIN Flight f 
            ON t.airline_name = f.airline_name
        AND t.flight_number = f.flight_number
        WHERE t.airline_name = %s
            AND p.purchase_time >= DATE_SUB(NOW(), INTERVAL 1 YEAR)
        GROUP BY f.arrival_airport
        ORDER BY cnt DESC
        LIMIT 3
    """, (airline,))
    y1 = cur.fetchall()

    cur.close(); conn.close()
    return render_template('staff_top_destinations.html',
                           last3=m3, last12=y1,
                           title='Top Destinations')


@app.route('/staff/grant_permissions', methods=['GET', 'POST'])
@staff_required
@permission_required('Admin')
def staff_grant_permissions():
    """
    Grant a new permission_type to a staff user in the same airline.
    """
    username = session['username']
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Fetch the airline the staff belongs to
    cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
    airline = cur.fetchone()['airline_name']

    # Define valid permission types
    permission_types = ['Admin', 'Operator']

    message = None
    if request.method == 'POST':
        target_username = request.form['staff_username']
        permission_type = request.form['permission_type']

        if permission_type not in permission_types:
            message = f"Invalid permission: {permission_type}"
        else:
            try:
                # Fetch the staff_email for the target username
                cur.execute("""
                    SELECT staff_email
                    FROM Airline_staff
                    WHERE username = %s AND airline_name = %s
                """, (target_username, airline))
                staff_email = cur.fetchone()

                if not staff_email:
                    message = f"Staff user '{target_username}' not found in this airline."
                else:
                    staff_email = staff_email['staff_email']

                    # Insert the permission into Permission_status
                    cur2 = conn.cursor()
                    cur2.execute("""
                        INSERT INTO Permission_status (username, staff_email, permission_type)
                        VALUES (%s, %s, %s)
                    """, (target_username, staff_email, permission_type))
                    conn.commit()
                    message = "Permission granted successfully."
                    cur2.close()
            except Exception as e:
                conn.rollback()
                message = f"Error: {e}"

    # List all staff in this airline
    cur.execute("""
        SELECT username, staff_email
        FROM Airline_staff
        WHERE airline_name = %s
    """, (airline,))
    staffs = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        'staff_grant_permissions.html',
        staffs=staffs,
        permission_types=permission_types,
        message=message,
        title='Grant Permissions'
    )


@app.route('/staff/add_booking_agents', methods=['GET','POST'])
@staff_required
@permission_required('Admin', 'Operator')
def staff_add_booking_agents():
    """
    Associate an existing Booking_agent with this airline.
    """
    username = session['username']
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT airline_name FROM Airline_staff WHERE staff_email=%s", (username,))
    airline = cur.fetchone()[0]

    message = None
    if request.method=='POST':
        agent_email = request.form['agent_email']
        try:
            cur.execute("""
              INSERT INTO Agent_status (agent_email, airline_name)
              VALUES (%s, %s)
            """, (agent_email, airline))
            conn.commit()
            message = "Booking agent added."
        except Exception as e:
            conn.rollback()
            message = f"Error: {e}"

    cur.close(); conn.close()
    return render_template('staff_add_booking_agents.html',
                           message=message,
                           title='Add Booking Agents')

if __name__ == '__main__':
    app.run(debug=True)