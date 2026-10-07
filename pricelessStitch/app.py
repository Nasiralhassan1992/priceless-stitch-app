import os
import sqlite3
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from urllib.parse import unquote

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
    redirect,
    url_for,
    session
)

from pdf_generator import (
    generate_admission_letter,
    generate_client_invoice
)

from werkzeug.utils import secure_filename

import psycopg2
from psycopg2.extras import RealDictCursor


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

app.secret_key = "priceless_stitch"

ADMIN_PASSWORD = "pricelessstitch1992"


# ============================================================
# UPLOAD CONFIGURATION
# ============================================================

UPLOAD_FOLDER = os.path.join("static", "uploads")

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ============================================================
# GENERATED PDF DIRECTORY
# ============================================================

PDF_DIR = os.path.join(
    app.root_path,
    "generated_pdfs"
)

os.makedirs(
    PDF_DIR,
    exist_ok=True
)
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db_connection():
    """
    Use PostgreSQL/Supabase on Render.
    Use SQLite locally when DATABASE_URL is not available.
    """

    if DATABASE_URL:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor
        )
        return conn

    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    conn = get_db_connection()
    cursor = conn.cursor()

    is_postgres = bool(DATABASE_URL)

    pk_type = (
        "SERIAL PRIMARY KEY"
        if is_postgres
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )

    # --------------------------------------------------------
    # 1. BOOKINGS
    # --------------------------------------------------------

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS bookings (
            id {pk_type},
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
    """)

    # --------------------------------------------------------
    # 2. STUDENTS
    # --------------------------------------------------------

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS students (
            id {pk_type},
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
    """)

    # Add missing columns to older databases if necessary.

    try:
        cursor.execute(
            "ALTER TABLE students ADD COLUMN start_date TEXT"
        )
    except Exception:
        pass

    try:
        cursor.execute(
            "ALTER TABLE students ADD COLUMN end_date TEXT"
        )
    except Exception:
        pass

    try:
        cursor.execute(
            "ALTER TABLE students ADD COLUMN status TEXT DEFAULT 'Active'"
        )
    except Exception:
        pass

    # --------------------------------------------------------
    # 3. MEASUREMENTS
    # --------------------------------------------------------

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS measurements (
            id {pk_type},
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
            FOREIGN KEY (booking_id)
                REFERENCES bookings (id)
        )
    """)

    # --------------------------------------------------------
    # 4. STAFF
    # --------------------------------------------------------

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS staff (
            id {pk_type},
            full_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            pay_type TEXT NOT NULL,
            salary_rate REAL DEFAULT 0.0,
            status TEXT DEFAULT 'Active'
        )
    """)

    # --------------------------------------------------------
    # 5. MACHINES
    # --------------------------------------------------------

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS machines (
            id {pk_type},
            machine_name TEXT NOT NULL,
            serial_number TEXT UNIQUE,
            status TEXT DEFAULT 'Working',
            assigned_staff_id INTEGER,
            FOREIGN KEY (assigned_staff_id)
                REFERENCES staff (id)
        )
    """)

    # --------------------------------------------------------
    # 6. WORK LOGS
    # --------------------------------------------------------

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS work_logs (
            id {pk_type},
            staff_id INTEGER NOT NULL,
            order_id TEXT,
            task_description TEXT NOT NULL,
            pieces_completed INTEGER DEFAULT 1,
            rate_per_piece REAL DEFAULT 0.0,
            date_logged DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (staff_id)
                REFERENCES staff (id)
        )
    """)

    # --------------------------------------------------------
    # 7. PAYROLL
    # --------------------------------------------------------

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS payroll (
            id {pk_type},
            staff_id INTEGER NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            total_earned REAL NOT NULL,
            amount_paid REAL NOT NULL,
            payment_date DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (staff_id)
                REFERENCES staff (id)
        )
    """)

    # --------------------------------------------------------
    # 8. STYLES
    # --------------------------------------------------------

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS styles (
            id {pk_type},
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            image_url TEXT NOT NULL,
            description TEXT
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# PUBLIC PAGES
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/academy")
def academy():
    return render_template("academy.html")


# ============================================================
# AUTHENTICATION
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        password = request.form.get("password")

        if password == ADMIN_PASSWORD:

            session["admin_logged_in"] = True

            return redirect(
                url_for("admin_portal")
            )

        return render_template(
            "login.html",
            error="Invalid admin password. Please try again."
        )

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.pop("admin_logged_in", None)

    return redirect(
        url_for("login")
    )


@app.route("/admin")
def admin_portal():

    if not session.get("admin_logged_in"):

        return redirect(
            url_for("login")
        )

    return render_template("admin.html")


# ============================================================
# CLIENT BOOKINGS API
# ============================================================

@app.route("/api/book", methods=["POST"])
def create_booking():

    data = request.get_json() or {}

    full_name = data.get("full_name")
    phone = data.get("phone")
    email = data.get("email")
    garment_type = data.get("garment_type")

    delivery_date = data.get(
        "delivery_date",
        "N/A"
    )

    total_price = float(
        data.get("total_price", 0.0)
    )

    down_payment = float(
        data.get("down_payment", 0.0)
    )

    notes = data.get("notes")

    if not full_name or not phone:

        return jsonify({
            "error": "Name and phone number are required."
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"

    try:

        cursor.execute(
            f"""
            INSERT INTO bookings (
                full_name,
                phone,
                email,
                garment_type,
                delivery_date,
                total_price,
                down_payment,
                notes
            )
            VALUES (
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph}
            )
            """,
            (
                full_name,
                phone,
                email,
                garment_type,
                delivery_date,
                total_price,
                down_payment,
                notes
            )
        )

        conn.commit()

        return jsonify({
            "message": "Booking submitted successfully!"
        }), 201

    except Exception as e:

        conn.rollback()

        return jsonify({
            "error": str(e)
        }), 500

    finally:

        conn.close()


@app.route("/api/bookings", methods=["GET"])
def get_bookings():

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                full_name,
                phone,
                email,
                garment_type,
                status,
                created_at
            FROM bookings
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        bookings = []

        for row in rows:

            item = dict(row)

            created_at = item.get(
                "created_at"
            )

            if created_at and hasattr(
                created_at,
                "strftime"
            ):
                item["created_at"] = created_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            elif created_at:

                item["created_at"] = str(
                    created_at
                )

            else:

                item["created_at"] = ""

            bookings.append(item)

        return jsonify(bookings), 200

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

    finally:

        conn.close()


@app.route(
    "/api/bookings/update_status",
    methods=["POST"]
)
def update_booking_status():

    data = request.get_json() or {}

    booking_id = data.get(
        "booking_id"
    )

    new_status = data.get(
        "status"
    )

    if not booking_id or not new_status:

        return jsonify({
            "error": "Missing booking_id or status"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    ph = "%s" if DATABASE_URL else "?"

    try:

        cursor.execute(
            f"""
            UPDATE bookings
            SET status = {ph}
            WHERE id = {ph}
            """,
            (
                new_status,
                booking_id
            )
        )

        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Status updated successfully!"
        }), 200

    except Exception as e:

        conn.rollback()

        return jsonify({
            "error": str(e)
        }), 500

    finally:

        conn.close()


# ============================================================
# END OF PART 1
# ============================================================

# ============================================================
# MEASUREMENTS API
# ============================================================

@app.route("/api/measurements/<int:booking_id>", methods=["GET"])
def get_measurement(booking_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            SELECT *
            FROM measurements
            WHERE booking_id = {ph}
            """,
            (booking_id,)
        )

        measurement = cursor.fetchone()

        if not measurement:
            return jsonify({
                "message": "No measurements found"
            }), 404

        if isinstance(measurement, dict):
            result = dict(measurement)
        else:
            result = dict(measurement)

        return jsonify(result), 200

    except Exception as e:
        print("GET MEASUREMENT ERROR:", e)
        return jsonify({
            "message": "Failed to load measurements",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/measurements/save", methods=["POST"])
def save_measurements():
    data = request.get_json(silent=True) or {}

    booking_id = data.get("booking_id")

    if not booking_id:
        return jsonify({
            "message": "booking_id is required"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        # Check whether measurements already exist
        cursor.execute(
            f"""
            SELECT id
            FROM measurements
            WHERE booking_id = {ph}
            """,
            (booking_id,)
        )

        existing = cursor.fetchone()

        fields = [
            "neck",
            "shoulder",
            "chest",
            "waist",
            "hip",
            "sleeve",
            "armhole",
            "bicep",
            "wrist",
            "length",
            "trouser_waist",
            "thigh",
            "knee",
            "bottom",
            "inseam",
            "outseam"
        ]

        values = [data.get(field) for field in fields]

        if existing:
            set_clause = ", ".join(
                f"{field} = {ph}" for field in fields
            )

            values.append(booking_id)

            cursor.execute(
                f"""
                UPDATE measurements
                SET {set_clause}
                WHERE booking_id = {ph}
                """,
                tuple(values)
            )

        else:
            columns = ["booking_id"] + fields
            placeholders = ", ".join([ph] * len(columns))

            values = [booking_id] + values

            cursor.execute(
                f"""
                INSERT INTO measurements
                ({", ".join(columns)})
                VALUES ({placeholders})
                """,
                tuple(values)
            )

        conn.commit()

        return jsonify({
            "message": "Measurements saved successfully"
        }), 200

    except Exception as e:
        conn.rollback()

        print("SAVE MEASUREMENTS ERROR:", e)

        return jsonify({
            "message": "Failed to save measurements",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# STYLES API
# ============================================================

@app.route("/api/styles", methods=["GET"])
def get_styles():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM styles
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        styles = []

        for row in rows:
            if isinstance(row, dict):
                styles.append(dict(row))
            else:
                styles.append(dict(row))

        return jsonify(styles), 200

    except Exception as e:
        print("GET STYLES ERROR:", e)

        return jsonify({
            "message": "Failed to load styles",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/styles", methods=["POST"])
def create_style():
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    description = data.get("description", "")
    image = data.get("image", "")

    if not name:
        return jsonify({
            "message": "Style name is required"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            INSERT INTO styles
            (name, description, image)
            VALUES ({ph}, {ph}, {ph})
            """,
            (name, description, image)
        )

        conn.commit()

        return jsonify({
            "message": "Style created successfully"
        }), 201

    except Exception as e:
        conn.rollback()

        print("CREATE STYLE ERROR:", e)

        return jsonify({
            "message": "Failed to create style",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/styles/<int:style_id>", methods=["DELETE"])
def delete_style(style_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            DELETE FROM styles
            WHERE id = {ph}
            """,
            (style_id,)
        )

        if cursor.rowcount == 0:
            conn.rollback()

            return jsonify({
                "message": "Style not found"
            }), 404

        conn.commit()

        return jsonify({
            "message": "Style deleted successfully"
        }), 200

    except Exception as e:
        conn.rollback()

        print("DELETE STYLE ERROR:", e)

        return jsonify({
            "message": "Failed to delete style",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# STUDENT REGISTRATION API
# ============================================================

@app.route("/api/students/register", methods=["POST"])
def register_student():
    data = request.get_json(silent=True) or {}

    full_name = data.get("full_name")
    phone = data.get("phone")
    email = data.get("email", "")
    program = data.get("program")
    duration = data.get("duration", "3 Months")
    start_date = data.get("start_date")
    tuition_fee = data.get("tuition_fee", 0)
    amount_paid = data.get("amount_paid", 0)

    if not full_name:
        return jsonify({
            "message": "Full name is required"
        }), 400

    if not phone:
        return jsonify({
            "message": "Phone is required"
        }), 400

    if not program:
        return jsonify({
            "message": "Program is required"
        }), 400

    if not start_date:
        return jsonify({
            "message": "Start date is required"
        }), 400

    # --------------------------------------------------------
    # Validate start date
    # --------------------------------------------------------

    try:
        start_dt = datetime.strptime(
            start_date,
            "%Y-%m-%d"
        ).date()

    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid start_date. Use YYYY-MM-DD."
        }), 400

    # --------------------------------------------------------
    # Calculate end date
    # --------------------------------------------------------

    duration_map = {
        "3 Months": 3,
        "6 Months": 6,
        "1 Year": 12
    }

    if duration not in duration_map:
        return jsonify({
            "message": "Invalid duration"
        }), 400

    end_dt = start_dt + relativedelta(
        months=duration_map[duration]
    )

    # --------------------------------------------------------
    # Validate payment amounts
    # --------------------------------------------------------

    try:
        tuition_fee = float(tuition_fee or 0)
        amount_paid = float(amount_paid or 0)

    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid tuition fee or amount paid"
        }), 400

    if tuition_fee < 0 or amount_paid < 0:
        return jsonify({
            "message": "Payment amounts cannot be negative"
        }), 400

    if amount_paid > tuition_fee:
        return jsonify({
            "message": "Amount paid cannot exceed tuition fee"
        }), 400

    # --------------------------------------------------------
    # Payment status
    # --------------------------------------------------------

    if tuition_fee == 0:
        payment_status = "Pending"
    elif amount_paid >= tuition_fee:
        payment_status = "Completed"
    elif amount_paid > 0:
        payment_status = "Partial"
    else:
        payment_status = "Pending"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        # ----------------------------------------------------
        # Generate registration number
        # ----------------------------------------------------

        cursor.execute("""
            SELECT COALESCE(MAX(id), 0) AS max_id
            FROM students
        """)

        row = cursor.fetchone()

        max_id = int(row["max_id"] or 0) if row else 0

        reg_number = f"PSA-2026-{max_id + 1:03d}"

        # ----------------------------------------------------
        # Insert student
        # ----------------------------------------------------

        cursor.execute(
            f"""
            INSERT INTO students
            (
                reg_number,
                full_name,
                phone,
                email,
                program,
                duration,
                start_date,
                end_date,
                tuition_fee,
                amount_paid,
                payment_status,
                registered_at
            )
            VALUES (
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                {ph},
                CURRENT_TIMESTAMP
            )
            """,
            (
                reg_number,
                full_name,
                phone,
                email,
                program,
                duration,
                start_dt.isoformat(),
                end_dt.isoformat(),
                tuition_fee,
                amount_paid,
                payment_status
            )
        )

        conn.commit()

        return jsonify({
            "message": "Registration successful!",
            "reg_number": reg_number
        }), 201

    except Exception as e:
        conn.rollback()

        print("REGISTER STUDENT ERROR:", e)

        return jsonify({
            "message": "Failed to register student",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# GET ALL STUDENTS
# ============================================================

@app.route("/api/students", methods=["GET"])
def get_students():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                id,
                reg_number,
                full_name,
                phone,
                email,
                program,
                duration,
                start_date,
                end_date,
                tuition_fee,
                amount_paid,
                payment_status,
                registered_at
            FROM students
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        students = []

        for row in rows:
            student = dict(row)

            # Convert date/datetime objects to JSON-safe strings
            for key, value in student.items():
                if hasattr(value, "isoformat"):
                    student[key] = value.isoformat()

            students.append(student)

        return jsonify(students), 200

    except Exception as e:
        print("GET STUDENTS ERROR:", e)

        return jsonify({
            "message": "Failed to load students",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# RECORD STUDENT PAYMENT
# ============================================================

@app.route("/api/students/record_payment", methods=["POST"])
def record_student_payment():
    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id")
    payment_amount = data.get("amount")

    if not student_id:
        return jsonify({
            "message": "student_id is required"
        }), 400

    try:
        payment_amount = float(payment_amount)

    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid payment amount"
        }), 400

    if payment_amount <= 0:
        return jsonify({
            "message": "Payment amount must be greater than zero"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            SELECT tuition_fee, amount_paid
            FROM students
            WHERE id = {ph}
            """,
            (student_id,)
        )

        student = cursor.fetchone()

        if not student:
            return jsonify({
                "message": "Student not found"
            }), 404

        tuition_fee = float(student["tuition_fee"] or 0)
        current_paid = float(student["amount_paid"] or 0)

        new_amount_paid = current_paid + payment_amount

        if new_amount_paid > tuition_fee:
            return jsonify({
                "message": "Payment exceeds outstanding balance"
            }), 400

        if tuition_fee > 0 and new_amount_paid >= tuition_fee:
            payment_status = "Completed"
        elif new_amount_paid > 0:
            payment_status = "Partial"
        else:
            payment_status = "Pending"

        cursor.execute(
            f"""
            UPDATE students
            SET
                amount_paid = {ph},
                payment_status = {ph}
            WHERE id = {ph}
            """,
            (
                new_amount_paid,
                payment_status,
                student_id
            )
        )

        conn.commit()

        return jsonify({
            "message": "Payment recorded successfully",
            "amount_paid": new_amount_paid,
            "payment_status": payment_status
        }), 200

    except Exception as e:
        conn.rollback()

        print("RECORD STUDENT PAYMENT ERROR:", e)

        return jsonify({
            "message": "Failed to record payment",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()
		
# ============================================================
# ADMISSION PDF
# ============================================================

@app.route("/api/pdf/admission/<string:reg_number>", methods=["GET"])
def download_admission(reg_number):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        clean_reg_number = unquote(reg_number)
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            SELECT *
            FROM students
            WHERE reg_number = {ph}
            """,
            (clean_reg_number,)
        )

        student = cursor.fetchone()

        if not student:
            return jsonify({
                "message": "Student not found"
            }), 404

        student = dict(student)

        pdf_filename = (
            f"Admission_{secure_filename(clean_reg_number)}.pdf"
        )

        pdf_path = os.path.join(
            PDF_DIR,
            pdf_filename
        )

        generate_admission_letter(
            pdf_path,
            student
		)

        if not os.path.exists(pdf_path):
            return jsonify({
                "message": "Admission PDF was not generated"
            }), 500

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_filename,
            mimetype="application/pdf"
        )

    except Exception as e:
        print("ADMISSION PDF ERROR:", e)

        return jsonify({
            "message": "Failed to generate admission letter",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# INVOICE PDF
# ============================================================

@app.route("/api/pdf/invoice/<int:booking_id>", methods=["GET"])
def download_invoice(booking_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            SELECT
                id,
                full_name,
                phone,
                garment_type,
                status,
                created_at,
                delivery_date,
                total_price,
                down_payment
            FROM bookings
            WHERE id = {ph}
            """,
            (booking_id,)
        )

        booking = cursor.fetchone()

        if not booking:
            return jsonify({
                "message": "Booking not found"
            }), 404

        booking = dict(booking)

        cursor.execute(
            f"""
            SELECT *
            FROM measurements
            WHERE booking_id = {ph}
            """,
            (booking_id,)
        )

        measurement = cursor.fetchone()

        if measurement:
            measurement = dict(measurement)
        else:
            measurement = {}

        pdf_filename = f"Invoice_Order_{booking_id}.pdf"

        pdf_path = os.path.join(
            PDF_DIR,
            pdf_filename
        )

        generate_client_invoice(
            pdf_path,
            booking,
            measurement
		)

        if not os.path.exists(pdf_path):
            return jsonify({
                "message": "Invoice PDF was not generated"
            }), 500

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_filename,
            mimetype="application/pdf"
        )

    except Exception as e:
        print("INVOICE PDF ERROR:", e)

        return jsonify({
            "message": "Failed to generate invoice",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# STAFF API
# ============================================================

@app.route("/api/staff", methods=["GET"])
def get_staff():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM staff
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        staff = []

        for row in rows:
            item = dict(row)

            for key, value in item.items():
                if hasattr(value, "isoformat"):
                    item[key] = value.isoformat()

            staff.append(item)

        return jsonify(staff), 200

    except Exception as e:
        print("GET STAFF ERROR:", e)

        return jsonify({
            "message": "Failed to load staff",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/staff", methods=["POST"])
def create_staff():
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    role = data.get("role", "")
    phone = data.get("phone", "")
    salary = data.get("salary", 0)
    status = data.get("status", "Active")

    if not name:
        return jsonify({
            "message": "Staff name is required"
        }), 400

    try:
        salary = float(salary or 0)
    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid salary"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            INSERT INTO staff
            (name, role, phone, salary, status)
            VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
            """,
            (
                name,
                role,
                phone,
                salary,
                status
            )
        )

        conn.commit()

        return jsonify({
            "message": "Staff created successfully"
        }), 201

    except Exception as e:
        conn.rollback()

        print("CREATE STAFF ERROR:", e)

        return jsonify({
            "message": "Failed to create staff",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/staff/<int:staff_id>", methods=["PUT", "DELETE"])
def manage_staff(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        # ----------------------------------------------------
        # DELETE
        # ----------------------------------------------------

        if request.method == "DELETE":
            cursor.execute(
                f"""
                DELETE FROM staff
                WHERE id = {ph}
                """,
                (staff_id,)
            )

            if cursor.rowcount == 0:
                conn.rollback()

                return jsonify({
                    "message": "Staff member not found"
                }), 404

            conn.commit()

            return jsonify({
                "message": "Staff deleted successfully"
            }), 200

        # ----------------------------------------------------
        # UPDATE
        # ----------------------------------------------------

        data = request.get_json(silent=True) or {}

        name = data.get("name")
        role = data.get("role")
        phone = data.get("phone")
        salary = data.get("salary")
        status = data.get("status")

        fields = []
        values = []

        if name is not None:
            fields.append(f"name = {ph}")
            values.append(name)

        if role is not None:
            fields.append(f"role = {ph}")
            values.append(role)

        if phone is not None:
            fields.append(f"phone = {ph}")
            values.append(phone)

        if salary is not None:
            try:
                salary = float(salary)
            except (ValueError, TypeError):
                return jsonify({
                    "message": "Invalid salary"
                }), 400

            fields.append(f"salary = {ph}")
            values.append(salary)

        if status is not None:
            fields.append(f"status = {ph}")
            values.append(status)

        if not fields:
            return jsonify({
                "message": "No fields supplied for update"
            }), 400

        values.append(staff_id)

        cursor.execute(
            f"""
            UPDATE staff
            SET {", ".join(fields)}
            WHERE id = {ph}
            """,
            tuple(values)
        )

        if cursor.rowcount == 0:
            conn.rollback()

            return jsonify({
                "message": "Staff member not found"
            }), 404

        conn.commit()

        return jsonify({
            "message": "Staff updated successfully"
        }), 200

    except Exception as e:
        conn.rollback()

        print("MANAGE STAFF ERROR:", e)

        return jsonify({
            "message": "Failed to update staff",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# STAFF STATUS
# ============================================================

@app.route("/api/staff/<int:staff_id>/status", methods=["PUT"])
def update_staff_status(staff_id):
    data = request.get_json(silent=True) or {}

    status = data.get("status")

    if not status:
        return jsonify({
            "message": "Status is required"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            UPDATE staff
            SET status = {ph}
            WHERE id = {ph}
            """,
            (
                status,
                staff_id
            )
        )

        if cursor.rowcount == 0:
            conn.rollback()

            return jsonify({
                "message": "Staff member not found"
            }), 404

        conn.commit()

        return jsonify({
            "message": "Staff status updated successfully"
        }), 200

    except Exception as e:
        conn.rollback()

        print("UPDATE STAFF STATUS ERROR:", e)

        return jsonify({
            "message": "Failed to update staff status",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# STAFF EARNINGS
# ============================================================

@app.route("/api/staff/<int:staff_id>/earnings", methods=["GET"])
def get_staff_earnings(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            SELECT *
            FROM work_logs
            WHERE staff_id = {ph}
            ORDER BY id DESC
            """,
            (staff_id,)
        )

        rows = cursor.fetchall()

        earnings = []

        for row in rows:
            item = dict(row)

            for key, value in item.items():
                if hasattr(value, "isoformat"):
                    item[key] = value.isoformat()

            earnings.append(item)

        return jsonify(earnings), 200

    except Exception as e:
        print("GET STAFF EARNINGS ERROR:", e)

        return jsonify({
            "message": "Failed to load staff earnings",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# WORK LOG
# ============================================================

@app.route("/api/work/log", methods=["POST"])
def log_work():
    data = request.get_json(silent=True) or {}

    staff_id = data.get("staff_id")
    booking_id = data.get("booking_id")
    amount = data.get("amount", 0)
    description = data.get("description", "")

    if not staff_id:
        return jsonify({
            "message": "staff_id is required"
        }), 400

    try:
        amount = float(amount or 0)
    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid amount"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            INSERT INTO work_logs
            (
                staff_id,
                booking_id,
                amount,
                description,
                created_at
            )
            VALUES (
                {ph},
                {ph},
                {ph},
                {ph},
                CURRENT_TIMESTAMP
            )
            """,
            (
                staff_id,
                booking_id,
                amount,
                description
            )
        )

        conn.commit()

        return jsonify({
            "message": "Work logged successfully"
        }), 201

    except Exception as e:
        conn.rollback()

        print("LOG WORK ERROR:", e)

        return jsonify({
            "message": "Failed to log work",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()

# ============================================================
# MACHINES API
# ============================================================

@app.route("/api/machines", methods=["GET"])
def get_machines():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM machines
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        machines = []

        for row in rows:
            item = dict(row)

            for key, value in item.items():
                if hasattr(value, "isoformat"):
                    item[key] = value.isoformat()

            machines.append(item)

        return jsonify(machines), 200

    except Exception as e:
        print("GET MACHINES ERROR:", e)

        return jsonify({
            "message": "Failed to load machines",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/machines", methods=["POST"])
def create_machine():
    data = request.get_json(silent=True) or {}

    name = data.get("name")
    machine_type = data.get("machine_type", "")
    status = data.get("status", "Working")

    if not name:
        return jsonify({
            "message": "Machine name is required"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            INSERT INTO machines
            (name, machine_type, status)
            VALUES ({ph}, {ph}, {ph})
            """,
            (
                name,
                machine_type,
                status
            )
        )

        conn.commit()

        return jsonify({
            "message": "Machine created successfully"
        }), 201

    except Exception as e:
        conn.rollback()

        print("CREATE MACHINE ERROR:", e)

        return jsonify({
            "message": "Failed to create machine",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# MACHINE ASSIGNMENT
# ============================================================

@app.route("/api/machines/<int:machine_id>/assign", methods=["PUT"])
def assign_machine(machine_id):
    data = request.get_json(silent=True) or {}

    staff_id = data.get("staff_id")

    if not staff_id:
        return jsonify({
            "message": "staff_id is required"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            UPDATE machines
            SET assigned_to = {ph}
            WHERE id = {ph}
            """,
            (
                staff_id,
                machine_id
            )
        )

        if cursor.rowcount == 0:
            conn.rollback()

            return jsonify({
                "message": "Machine not found"
            }), 404

        conn.commit()

        return jsonify({
            "message": "Machine assigned successfully"
        }), 200

    except Exception as e:
        conn.rollback()

        print("ASSIGN MACHINE ERROR:", e)

        return jsonify({
            "message": "Failed to assign machine",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# MACHINE STATUS
# ============================================================

@app.route("/api/machines/<int:machine_id>/status", methods=["PUT"])
def update_machine_status(machine_id):
    data = request.get_json(silent=True) or {}

    status = data.get("status", "Working")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            UPDATE machines
            SET status = {ph}
            WHERE id = {ph}
            """,
            (
                status,
                machine_id
            )
        )

        if cursor.rowcount == 0:
            conn.rollback()

            return jsonify({
                "message": "Machine not found"
            }), 404

        conn.commit()

        return jsonify({
            "message": "Machine status updated successfully"
        }), 200

    except Exception as e:
        conn.rollback()

        print("UPDATE MACHINE STATUS ERROR:", e)

        return jsonify({
            "message": "Failed to update machine status",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# PAYROLL
# ============================================================

@app.route("/api/payroll", methods=["GET"])
def get_payroll():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT *
            FROM payroll
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        payroll = []

        for row in rows:
            item = dict(row)

            for key, value in item.items():
                if hasattr(value, "isoformat"):
                    item[key] = value.isoformat()

            payroll.append(item)

        return jsonify(payroll), 200

    except Exception as e:
        print("GET PAYROLL ERROR:", e)

        return jsonify({
            "message": "Failed to load payroll",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/payroll", methods=["POST"])
def create_payroll():
    data = request.get_json(silent=True) or {}

    staff_id = data.get("staff_id")
    amount = data.get("amount")
    period = data.get("period", "")
    status = data.get("status", "Pending")

    if not staff_id:
        return jsonify({
            "message": "staff_id is required"
        }), 400

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({
            "message": "Invalid payroll amount"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ph = "%s" if DATABASE_URL else "?"

        cursor.execute(
            f"""
            INSERT INTO payroll
            (staff_id, amount, period, status)
            VALUES ({ph}, {ph}, {ph}, {ph})
            """,
            (
                staff_id,
                amount,
                period,
                status
            )
        )

        conn.commit()

        return jsonify({
            "message": "Payroll created successfully"
        }), 201

    except Exception as e:
        conn.rollback()

        print("CREATE PAYROLL ERROR:", e)

        return jsonify({
            "message": "Failed to create payroll",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


# ============================================================
# ROUTE DIAGNOSTICS
# ============================================================

def print_registered_routes():
    print("")
    print("==============================================")
    print("REGISTERED FLASK ROUTES")
    print("==============================================")

    for rule in app.url_map.iter_rules():
        methods = ",".join(
            sorted(
                method
                for method in rule.methods
                if method not in {"HEAD", "OPTIONS"}
            )
        )

        print(
            f"{methods:15} {rule.rule:50} "
            f"-> {rule.endpoint}"
        )

    print("==============================================")
    print("TOTAL ROUTES:", len(list(app.url_map.iter_rules())))
    print("==============================================")


# ============================================================
# APPLICATION STARTUP
# ============================================================

if __name__ == "__main__":
    print("==============================================")
    print("STARTING PRICELESS STITCH APPLICATION")
    print("APP FILE:", os.path.abspath(__file__))
    print("APP NAME:", app.name)
    print("==============================================")

    init_db()
    print_registered_routes()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )		
