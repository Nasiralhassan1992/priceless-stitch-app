import os
import sqlite3
import time
from flask import Flask, jsonify, render_template, request, send_file
from pdf_generator import generate_admission_letter, generate_client_invoice
from werkzeug.utils import secure_filename

app = Flask(__name__)


UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    #  1 Client Bookings Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            garment_type TEXT NOT NULL,
            delivery_date TEXT,
            total_price REAL DEFAULT 0.0,
            down_payment REAL DEFAULT 0.0,
            notes TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    #2 Student Registrations Table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_number TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            program TEXT NOT NULL,
            duration TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            tuition_fee REAL NOT NULL,
            amount_paid REAL DEFAULT 0.0,
            payment_status TEXT DEFAULT 'Pending',
            status TEXT DEFAULT 'Active',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    # Ensure start_date and end_date columns exist if table was already created
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN start_date TEXT")
    except Exception:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE students ADD COLUMN end_date TEXT")
    except Exception:
        pass  # Column already exists
    
    #3 Measurements Table Linked to Client Booking (All 14 fields)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER UNIQUE NOT NULL,
            length_shift REAL DEFAULT 0,
            shoulder REAL DEFAULT 0,
            neck REAL DEFAULT 0,
            chest REAL DEFAULT 0,
            sleeves REAL DEFAULT 0,
            tommy REAL DEFAULT 0,
            under_bust_round REAL DEFAULT 0,
            shoulder_to_under_bust REAL DEFAULT 0,
            trouser_length REAL DEFAULT 0,
            waist REAL DEFAULT 0,
            hips REAL DEFAULT 0,
            thigh REAL DEFAULT 0,
            knee REAL DEFAULT 0,
            ankle REAL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (booking_id) REFERENCES bookings (id)
        )
    """
    )
    
    # 4. Staff Registry
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL, -- Tailor, Instructor, Cutter, Finisher
            pay_type TEXT NOT NULL, -- Fixed Salary, Piece Rate
            salary_rate REAL DEFAULT 0.0,
            status TEXT DEFAULT 'Active'
        )
    ''')

    # 5. Sewing & Production Machinery
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_name TEXT NOT NULL, -- e.g. Industrial Straight Stitch #1
            serial_number TEXT UNIQUE,
            status TEXT DEFAULT 'Working', -- Working, Needs Service, Out of Service
            assigned_staff_id INTEGER,
            FOREIGN KEY (assigned_staff_id) REFERENCES staff (id)
        )
    ''')

    # 6. Work Done Log (Piece-Rate / Daily Tasks)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            order_id TEXT, -- Tied to client order if applicable
            task_description TEXT NOT NULL, -- e.g., Trouser Stitching, Cutting 5 Suits
            pieces_completed INTEGER DEFAULT 1,
            rate_per_piece REAL DEFAULT 0.0,
            date_logged DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (staff_id) REFERENCES staff (id)
        )
    ''')

    # 7. Payroll Records
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            total_earned REAL NOT NULL,
            amount_paid REAL NOT NULL,
            payment_date DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (staff_id) REFERENCES staff (id)
        )
    ''')

    #8. Styles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS styles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            image_url TEXT NOT NULL,
            description TEXT
        )
    ''')
       
    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/academy")
def academy():
    return render_template("academy.html")


@app.route("/admin")
def admin_portal():
    return render_template("admin.html")


# --- CLIENT BOOKINGS API ---
@app.route('/api/book', methods=['POST'])
def create_booking():
    data = request.json
    full_name = data.get('full_name')
    phone = data.get('phone')
    email = data.get('email')
    garment_type = data.get('garment_type')
    delivery_date = data.get('delivery_date', 'N/A')
    total_price = float(data.get('total_price', 0.0))
    down_payment = float(data.get('down_payment', 0.0))
    notes = data.get('notes')

    if not full_name or not phone:
        return jsonify({"error": "Name and phone number are required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO bookings (full_name, phone, email, garment_type, delivery_date, total_price, down_payment, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (full_name, phone, email, garment_type, delivery_date, total_price, down_payment, notes))
    conn.commit()
    conn.close()

    return jsonify({"message": "Booking submitted successfully!"}), 201


@app.route("/api/bookings", methods=["GET"])
def get_bookings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, full_name, phone, email, garment_type, status, created_at FROM bookings ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    conn.close()

    bookings = [
        {
            "id": row["id"],
            "full_name": row["full_name"],
            "phone": row["phone"],
            "email": row["email"],
            "garment_type": row["garment_type"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return jsonify(bookings)


# --- MEASUREMENTS API ---
@app.route("/api/measurements/<int:booking_id>", methods=["GET"])
def get_measurement(booking_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM measurements WHERE booking_id = ?", (booking_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify(dict(row))

    return (
        jsonify(
            {
                "length_shift": 0.0,
                "shoulder": 0.0,
                "neck": 0.0,
                "chest": 0.0,
                "sleeves": 0.0,
                "tommy": 0.0,
                "under_bust_round": 0.0,
                "shoulder_to_under_bust": 0.0,
                "trouser_length": 0.0,
                "waist": 0.0,
                "hips": 0.0,
                "thigh": 0.0,
                "knee": 0.0,
                "ankle": 0.0,
            }
        ),
        200,
    )


@app.route("/api/measurements/save", methods=["POST"])
def save_measurements():
    data = request.get_json()
    booking_id = data.get("booking_id")

    if not booking_id:
        return jsonify({"error": "booking_id is required"}), 400
    
    total_price = float(data.get('total_price', 0.0))
    down_payment = float(data.get('down_payment', 0.0))
    delivery_date = data.get('delivery_date', 'N/A')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Update Booking Financial Data & Status
    cursor.execute('''
        UPDATE bookings 
        SET total_price = ?, down_payment = ?,delivery_date = ?, status = 'In Progress' 
        WHERE id = ?
    ''', (total_price, down_payment,delivery_date, booking_id))

 
    # 2. Upsert Measurements
    query = """
    INSERT INTO measurements (
        booking_id, length_shift, shoulder, neck, chest, sleeves, tommy,
        under_bust_round, shoulder_to_under_bust, trouser_length, waist,
        hips, thigh, knee, ankle
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(booking_id) DO UPDATE SET
        length_shift = excluded.length_shift,
        shoulder = excluded.shoulder,
        neck = excluded.neck,
        chest = excluded.chest,
        sleeves = excluded.sleeves,
        tommy = excluded.tommy,
        under_bust_round = excluded.under_bust_round,
        shoulder_to_under_bust = excluded.shoulder_to_under_bust,
        trouser_length = excluded.trouser_length,
        waist = excluded.waist,
        hips = excluded.hips,
        thigh = excluded.thigh,
        knee = excluded.knee,
        ankle = excluded.ankle,
        updated_at = CURRENT_TIMESTAMP;
    """

    values = (
        booking_id,
        data.get("length_shift", 0),
        data.get("shoulder", 0),
        data.get("neck", 0),
        data.get("chest", 0),
        data.get("sleeves", 0),
        data.get("tommy", 0),
        data.get("under_bust_round", 0),
        data.get("shoulder_to_under_bust", 0),
        data.get("trouser_length", 0),
        data.get("waist", 0),
        data.get("hips", 0),
        data.get("thigh", 0),
        data.get("knee", 0),
        data.get("ankle", 0),
    )

    cursor.execute(query, values)

    # 2. Automatically update booking status to 'In Progress'
    cursor.execute(
        "UPDATE bookings SET status = 'In Progress' WHERE id = ?", (booking_id,)
    )

    conn.commit()
    conn.close()

    return (
        jsonify(
            {
                "status": "success",
                "message": "Measurements saved and status updated to In Progress.",
            }
        ),
        200,
    )
    
@app.route("/api/bookings/update_status", methods=["POST"])
def update_booking_status():
    data = request.get_json()
    booking_id = data.get("booking_id")
    new_status = data.get("status")

    if not booking_id or not new_status:
        return jsonify({"error": "Missing booking_id or status"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id)
    )
    conn.commit()
    conn.close()

    return (
        jsonify(
            {"status": "success", "message": "Status updated successfully!"}
        ),
        200,
    )
    
# API to GET all styles & POST new style
@app.route('/api/styles', methods=['GET', 'POST'])
def handle_styles():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            title = request.form.get('title')
            category = request.form.get('category')
            price = float(request.form.get('price', 0.0))
            description = request.form.get('description', '')

            if not title:
                conn.close()
                return jsonify({'error': 'Title is required.'}), 400

            if 'image' not in request.files:
                conn.close()
                return jsonify({'error': 'No image file uploaded.'}), 400

            file = request.files['image']
            if file.filename == '':
                conn.close()
                return jsonify({'error': 'No file selected.'}), 400

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{int(time.time())}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)

                image_url = f"/static/uploads/{unique_filename}"

                cursor.execute('''
                    INSERT INTO styles (title, category, price, image_url, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (title, category, price, image_url, description))
                
                conn.commit()
                conn.close()
                return jsonify({'message': 'Style added successfully!'}), 201
            else:
                conn.close()
                return jsonify({'error': 'File format not allowed.'}), 400

        except Exception as e:
            conn.close()
            print("\n[STYLE UPLOAD ERROR]:", str(e), "\n")
            return jsonify({'error': str(e)}), 500

    # GET Request
    try:
        cursor.execute('SELECT * FROM styles ORDER BY id DESC')
        styles = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(styles), 200
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
        
# DELETE A STYLE
@app.route('/api/styles/<int:style_id>', methods=['DELETE'])
def delete_style(style_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Optional: Retrieve file path first if you want to delete the file from disk
        cursor.execute('SELECT image_url FROM styles WHERE id = ?', (style_id,))
        style = cursor.fetchone()
        
        if style and style['image_url'].startswith('/static/uploads/'):
            file_path = os.path.join(app.root_path, style['image_url'].lstrip('/'))
            if os.path.exists(file_path):
                os.remove(file_path)

        cursor.execute('DELETE FROM styles WHERE id = ?', (style_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Style deleted successfully.'}), 200
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500        
    
from datetime import datetime
from dateutil.relativedelta import relativedelta


# --- STUDENT REGISTRATION API ---
@app.route("/api/students/register", methods=["POST"])
def register_student():
    data = request.json
    full_name = data.get("full_name")
    phone = data.get("phone")
    email = data.get("email")
    program = data.get("program")
    duration = data.get("duration")
    start_date_str = data.get("start_date")  # Extracted from frontend payload
    tuition_fee = float(data.get("tuition_fee", 0.0))
    amount_paid = float(data.get("amount_paid", 0.0))

    # Validate required fields including start_date
    if not full_name or not phone or not program or not start_date_str:
        return (
            jsonify(
                {
                    "error": "Full name, phone, program, and start date are required."
                }
            ),
            400,
        )

    # 1. Parse Start Date & Compute End Date
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")

    if "3 Months" in duration:
        end_dt = start_dt + relativedelta(months=3)
    elif "6 Months" in duration:
        end_dt = start_dt + relativedelta(months=6)
    elif "1 Year" in duration:
        end_dt = start_dt + relativedelta(years=1)
    else:
        end_dt = start_dt + relativedelta(months=3)

    end_date_str = end_dt.strftime("%Y-%m-%d")

    # 2. Database Insert Operations
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(id) FROM students")
    max_id = cursor.fetchone()[0] or 0
    reg_number = f"PSA-2026-{(max_id + 1):03d}"

    if amount_paid >= tuition_fee and tuition_fee > 0:
        pay_status = "Completed"
    elif amount_paid > 0:
        pay_status = "Partial"
    else:
        pay_status = "Pending"

    cursor.execute(
        """
        INSERT INTO students (
            reg_number, full_name, phone, email, program, duration, 
            start_date, end_date, tuition_fee, amount_paid, payment_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            reg_number,
            full_name,
            phone,
            email,
            program,
            duration,
            start_date_str,
            end_date_str,
            tuition_fee,
            amount_paid,
            pay_status,
        ),
    )

    conn.commit()
    conn.close()

    return (
        jsonify(
            {"message": "Registration successful!", "reg_number": reg_number}
        ),
        201,
    )


@app.route("/api/students", methods=["GET"])
def get_students():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, reg_number, full_name, phone, email, program, duration, tuition_fee, amount_paid, payment_status, status, registered_at 
        FROM students ORDER BY id DESC
    """
    )
    rows = cursor.fetchall()
    conn.close()

    students = [dict(row) for row in rows]
    return jsonify(students)


# Ensure pdfs output folder exists
PDF_DIR = os.path.join(app.root_path, "generated_pdfs")
os.makedirs(PDF_DIR, exist_ok=True)


@app.route("/api/pdf/invoice/<int:booking_id>", methods=["GET"])
def download_invoice(booking_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 👇 ADD total_price AND down_payment TO SELECT QUERY 👇
    cursor.execute(
        """
        SELECT id, full_name, phone, garment_type, status, created_at, delivery_date, total_price, down_payment 
        FROM bookings WHERE id = ?
    """,
        (booking_id,),
    )
    b = cursor.fetchone()

    if not b:
        conn.close()
        return jsonify({"error": "Booking not found"}), 404

    client_data = dict(b)

    cursor.execute(
        "SELECT * FROM measurements WHERE booking_id = ?", (booking_id,)
    )
    m = cursor.fetchone()
    conn.close()

    measurements = dict(m) if m else {}

    pdf_filename = f"Invoice_Order_{booking_id}.pdf"
    filepath = os.path.join(PDF_DIR, pdf_filename)

    generate_client_invoice(filepath, client_data, measurements)
    return send_file(filepath, as_attachment=True)


@app.route("/api/pdf/admission/<string:reg_number>", methods=["GET"])
def download_admission(reg_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT reg_number, full_name, phone, program, duration, 
               start_date, end_date, tuition_fee, amount_paid, payment_status, registered_at 
        FROM students WHERE reg_number = ?
    """,
        (reg_number,),
    )
    s = cursor.fetchone()
    conn.close()

    if not s:
        return jsonify({"error": "Student record not found"}), 404

    student_data = dict(s)

    pdf_filename = f"Admission_{reg_number}.pdf"
    filepath = os.path.join(PDF_DIR, pdf_filename)

    generate_admission_letter(filepath, student_data)
    return send_file(filepath, as_attachment=True)


@app.route("/api/students/record_payment", methods=["POST"])
def record_student_payment():
    data = request.get_json()
    reg_number = data.get("reg_number")

    if not reg_number:
        return jsonify({"error": "Invalid student registration number."}), 400

    try:
        payment_amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        payment_amount = 0.0

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT tuition_fee, amount_paid FROM students WHERE reg_number = ?",
        (reg_number,),
    )
    student = cursor.fetchone()

    if not student:
        conn.close()
        return jsonify({"error": "Student not found."}), 404

    # Resolve tuition fee from payload, falling back to existing database value
    raw_tuition = data.get("tuition_fee")
    try:
        tuition_fee = (
            float(raw_tuition)
            if raw_tuition is not None and raw_tuition != ""
            else student["tuition_fee"]
        )
    except (ValueError, TypeError):
        tuition_fee = student["tuition_fee"]

    current_paid = student["amount_paid"]
    new_paid = current_paid + payment_amount

    # Recalculate status dynamically
    if new_paid >= tuition_fee and tuition_fee > 0:
        new_status = "Completed"
    elif new_paid > 0:
        new_status = "Partial"
    else:
        new_status = "Pending"

    # Save updated record
    cursor.execute(
        """
        UPDATE students 
        SET tuition_fee = ?, amount_paid = ?, payment_status = ? 
        WHERE reg_number = ?
        """,
        (tuition_fee, new_paid, new_status, reg_number),
    )

    conn.commit()
    conn.close()

    return (
        jsonify(
            {
                "message": "Payment and tuition updated successfully.",
                "tuition_fee": tuition_fee,
                "new_amount_paid": new_paid,
                "payment_status": new_status,
            }
        ),
        200,
    )


# --- Log Work Done by Staff ---
@app.route('/api/work/log', methods=['POST'])
def log_staff_work():
    data = request.get_json()
    staff_id = data.get('staff_id')
    task = data.get('task_description')
    pieces = int(data.get('pieces_completed', 1))
    rate = float(data.get('rate_per_piece', 0.0))
    order_id = data.get('order_id')

    if not staff_id or not task:
        return jsonify({'error': 'Staff member and task description are required.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO work_logs (staff_id, order_id, task_description, pieces_completed, rate_per_piece)
        VALUES (?, ?, ?, ?, ?)
    ''', (staff_id, order_id, task, pieces, rate))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Work logged successfully.'}), 200

# --- Get Unpaid Earnings for a Staff Member ---
@app.route('/api/staff/<int:staff_id>/earnings', methods=['GET'])
def get_staff_earnings(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Calculate total earned from piecework logs
    cursor.execute('''
        SELECT SUM(pieces_completed * rate_per_piece) as piecework_total
        FROM work_logs 
        WHERE staff_id = ?
    ''', (staff_id,))
    work_total = cursor.fetchone()['piecework_total'] or 0.0

    # Calculate total payments already made
    cursor.execute('''
        SELECT SUM(amount_paid) as total_paid
        FROM payroll 
        WHERE staff_id = ?
    ''', (staff_id,))
    paid_total = cursor.fetchone()['total_paid'] or 0.0

    conn.close()
    
    balance_due = work_total - paid_total
    return jsonify({
        'total_earned': work_total,
        'total_paid': paid_total,
        'balance_due': balance_due
    }), 200
    
# --- STAFF MANAGEMENT ENDPOINTS ---
@app.route('/api/staff', methods=['GET', 'POST'])
def handle_staff():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            full_name = data.get('full_name')
            phone = data.get('phone')
            role = data.get('role', 'Tailor')
            pay_type = data.get('pay_type', 'Piece Rate')
            
            # Catch all casing possibilities (salary_rate, Salary_rate, rate)
            salary_rate = float(
                data.get('salary_rate') or
                data.get('Salary_rate') or
                data.get('rate') or 
                0.0
            )

            if not full_name or not phone:
                conn.close()
                return jsonify({'error': 'Name and phone number are required.'}), 400

            cursor.execute('''
                INSERT INTO staff (full_name, phone, role, pay_type, salary_rate, status)
                VALUES (?, ?, ?, ?, ?, 'Active')
            ''', (full_name, phone, role, pay_type, salary_rate))
            
            conn.commit()
            conn.close()
            return jsonify({'message': 'Staff added successfully.'}), 201

        except Exception as e:
            conn.close()
            print("\n[FLASK ERROR - POST /api/staff]:", str(e), "\n")
            return jsonify({'error': str(e)}), 500

    # GET REQUEST
    try:
        cursor.execute('SELECT id, full_name, phone, role, pay_type, salary_rate, status FROM staff ORDER BY id DESC')
        rows = cursor.fetchall()
        staff_list = [dict(row) for row in rows]
        conn.close()
        return jsonify(staff_list), 200

    except Exception as e:
        conn.close()
        print("\n[FLASK ERROR - GET /api/staff]:", str(e), "\n")
        return jsonify({'error': str(e)}), 500
        
# UPDATE STAFF DETAILS (or status directly)
@app.route('/api/staff/<int:staff_id>', methods=['PUT'])
def update_staff(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    data = request.get_json() or {}

    full_name = data.get('full_name')
    phone = data.get('phone')
    role = data.get('role')
    pay_type = data.get('pay_type')
    salary_rate = float(data.get('salary_rate') or data.get('rate') or 0.0)
    status = data.get('status', 'Active')

    try:
        cursor.execute('''
            UPDATE staff 
            SET full_name = ?, phone = ?, role = ?, pay_type = ?, salary_rate = ?, status = ?
            WHERE id = ?
        ''', (full_name, phone, role, pay_type, salary_rate, status, staff_id))
        
        conn.commit()
        conn.close()
        return jsonify({'message': 'Staff updated successfully.'}), 200
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

# TOGGLE STAFF STATUS (Active / Suspended)
@app.route('/api/staff/<int:staff_id>/status', methods=['PUT'])
def toggle_staff_status(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    data = request.get_json() or {}
    new_status = data.get('status')

    try:
        cursor.execute('UPDATE staff SET status = ? WHERE id = ?', (new_status, staff_id))
        conn.commit()
        conn.close()
        return jsonify({'message': f'Staff status changed to {new_status}.'}), 200
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

# DELETE STAFF
@app.route('/api/staff/<int:staff_id>', methods=['DELETE'])
def delete_staff(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM staff WHERE id = ?', (staff_id,))
        # Also clear machine assignments for deleted staff
        cursor.execute('UPDATE machines SET assigned_staff_id = NULL WHERE assigned_staff_id = ?', (staff_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Staff deleted successfully.'}), 200
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

# --- MACHINE INVENTORY ENDPOINTS ---
@app.route('/api/machines', methods=['GET', 'POST'])
def handle_machines():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.get_json() or {}
        machine_name = data.get('machine_name')
        serial_number = data.get('serial_number')
        status = data.get('status', 'Working')
        assigned_staff_id = data.get('assigned_staff_id') or None

        if not machine_name:
            conn.close()
            return jsonify({'error': 'Machine name is required.'}), 400

        try:
            cursor.execute('''
                INSERT INTO machines (machine_name, serial_number, status, assigned_staff_id)
                VALUES (?, ?, ?, ?)
            ''', (machine_name, serial_number, status, assigned_staff_id))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Machine added successfully.'}), 201
        except Exception as e:
            conn.close()
            return jsonify({'error': str(e)}), 500

    # GET Request: Fetch assigned_staff_id explicitly
    try:
        cursor.execute('''
            SELECT 
                m.id, 
                m.machine_name, 
                m.serial_number, 
                m.status, 
                m.assigned_staff_id,
                s.full_name AS assigned_staff
            FROM machines m
            LEFT JOIN staff s ON m.assigned_staff_id = s.id
            ORDER BY m.id DESC
        ''')
        rows = cursor.fetchall()
        machine_list = [dict(row) for row in rows]
        conn.close()
        return jsonify(machine_list), 200
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/machines/<int:machine_id>/assign', methods=['PUT'])
def assign_machine(machine_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    data = request.get_json() or {}
    
    assigned_staff_id = data.get('assigned_staff_id')
    if assigned_staff_id == '':
        assigned_staff_id = None

    try:
        cursor.execute('''
            UPDATE machines 
            SET assigned_staff_id = ? 
            WHERE id = ?
        ''', (assigned_staff_id, machine_id))
        
        conn.commit()
        conn.close()
        return jsonify({'message': 'Machine assigned successfully.'}), 200
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500 

@app.route('/api/machines/<int:machine_id>/status', methods=['PUT'])
def update_machine_status(machine_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    data = request.get_json() or {}
    
    new_status = data.get('status', 'Working')

    try:
        cursor.execute('''
            UPDATE machines 
            SET status = ? 
            WHERE id = ?
        ''', (new_status, machine_id))
        
        conn.commit()
        conn.close()
        return jsonify({'message': 'Machine status updated successfully.'}), 200
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500        

if __name__ == "__main__":
    init_db()
    app.run(host= '0.0.0.0', debug=True, port=5000)