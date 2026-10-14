import os
import re
import pandas as pd
import mysql.connector

from flask import Flask, request, jsonify, render_template_string
from mysql.connector import Error

app = Flask(__name__)

# -------------------------------
# 1. MySQL database configuration
# -------------------------------

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "student_db")
}

CSV_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "students.csv"
)

REQUIRED_COLUMNS = [
    "student_id", "name", "department",
    "age", "city", "marks"
]


# -------------------------------
# 2. Connect to MySQL
# -------------------------------

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


# -------------------------------
# 3. Create database and table
# -------------------------------

def setup_database():
    # Create database first, without selecting a database
    connection = mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"]
    )

    try:
        cursor = connection.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`"
        )
        cursor.close()
    finally:
        connection.close()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                department VARCHAR(100) NOT NULL,
                age INT NOT NULL,
                city VARCHAR(100) NOT NULL,
                marks DECIMAL(5, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()
        cursor.close()
    finally:
        connection.close()


# -------------------------------
# 4. Read and clean CSV data
# -------------------------------

def clean_csv_data():
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(
            f"CSV file not found: {CSV_FILE}"
        )

    df = pd.read_csv(CSV_FILE)

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing CSV columns: {sorted(missing_columns)}"
        )

    df = df[REQUIRED_COLUMNS].copy()

    # Clean text columns
    for column in ["name", "department", "city"]:
        df[column] = df[column].astype("string").str.strip()
        df[column] = df[column].replace("", pd.NA)

    # Convert numeric fields; invalid values become NaN
    for column in ["student_id", "age", "marks"]:
        df[column] = pd.to_numeric(
            df[column], errors="coerce"
        )

    # Remove rows with missing or invalid numeric values
    df = df.dropna(subset=REQUIRED_COLUMNS)

    # Numeric fields must be whole numbers where required
    for column in ["student_id", "age"]:
        df = df[df[column] % 1 == 0]

    # Apply sensible validation rules
    df = df[
        (df["student_id"] > 0)
        & (df["age"].between(1, 120))
        & (df["marks"].between(0, 100))
    ]

    # Skip blank text values
    df = df.dropna(subset=["name", "department", "city"])

    # Keep the first occurrence of duplicate student IDs
    df = df.drop_duplicates(
        subset=["student_id"], keep="first"
    )

    # Convert values into MySQL-compatible Python types
    df["student_id"] = df["student_id"].astype(int)
    df["age"] = df["age"].astype(int)
    df["marks"] = df["marks"].astype(float)

    return df


# -------------------------------
# 5. Load CSV records into MySQL
# -------------------------------

def load_students():
    df = clean_csv_data()

    connection = get_connection()

    inserted = 0
    skipped = 0

    try:
        cursor = connection.cursor()

        sql = """
            INSERT IGNORE INTO students
            (student_id, name, department, age, city, marks)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        for record in df.itertuples(index=False, name=None):
            cursor.execute(sql, record)

            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

        connection.commit()

        cursor.close()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    return {
        "valid_records": len(df),
        "inserted": inserted,
        "skipped_duplicates": skipped
    }


# -------------------------------
# 6. Fetch and search students
# -------------------------------

def search_students(search_term=""):
    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        sql = """
            SELECT student_id, name, department,
                   age, city, marks
            FROM students
        """

        if search_term:
            pattern = f"%{search_term}%"
            sql += """
                WHERE name LIKE %s
                   OR department LIKE %s
                   OR city LIKE %s
            """
            cursor.execute(sql, (pattern, pattern, pattern))
        else:
            cursor.execute(sql)

        rows = cursor.fetchall()
        cursor.close()

        # Convert Decimal marks into JSON-friendly numbers
        for row in rows:
            row["marks"] = float(row["marks"])

        return rows

    finally:
        connection.close()


# -------------------------------
# 7. Website homepage
# -------------------------------

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Student Data Management</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 35px;
            background: #f3f6fb;
            color: #172033;
        }
        h1 { color: #173f7a; }
        form { margin: 20px 0; }
        input {
            padding: 10px;
            width: 260px;
            max-width: 70%;
        }
        button, .link {
            padding: 10px 14px;
            background: #1756a9;
            color: white;
            border: none;
            text-decoration: none;
            cursor: pointer;
            border-radius: 4px;
        }
        .table-wrap { overflow-x: auto; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }
        th, td {
            border: 1px solid #d7deea;
            padding: 11px;
            text-align: left;
        }
        th { background: #1756a9; color: white; }
        tr:nth-child(even) { background: #edf3fc; }
        .info { margin: 15px 0; }
    </style>
</head>
<body>
    <h1>Student Data Management System</h1>
    <p>Search students by name, department, or city.</p>

    <form method="GET" action="/">
        <input name="q" value="{{ q }}"
               placeholder="Enter name, department, or city">
        <button type="submit">Search</button>
        <a class="link" href="/">Show All</a>
    </form>

    <p class="info">Students found: {{ students|length }}</p>

    <div class="table-wrap">
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Department</th>
                <th>Age</th>
                <th>City</th>
                <th>Marks</th>
            </tr>
        </thead>
        <tbody>
        {% for s in students %}
            <tr>
                <td>{{ s.student_id }}</td>
                <td>{{ s.name }}</td>
                <td>{{ s.department }}</td>
                <td>{{ s.age }}</td>
                <td>{{ s.city }}</td>
                <td>{{ "%.2f"|format(s.marks) }}</td>
            </tr>
        {% else %}
            <tr><td colspan="6">No students found.</td></tr>
        {% endfor %}
        </tbody>
    </table>
    </div>

    <p><a href="/api/students">View all students as JSON API</a></p>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def home():
    query = request.args.get("q", "").strip()
    students = search_students(query)

    return render_template_string(
        HTML_PAGE, students=students, q=query
    )


# -------------------------------
# 8. REST API for student records
# -------------------------------

@app.route("/api/students", methods=["GET"])
def students_api():
    query = request.args.get("q", "").strip()

    return jsonify({
        "count": len(search_students(query)),
        "students": search_students(query)
    })


@app.route("/api/students/<int:student_id>", methods=["GET"])
def student_by_id(student_id):
    connection = get_connection()

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT student_id, name, department,
                   age, city, marks
            FROM students
            WHERE student_id = %s
        """, (student_id,))

        student = cursor.fetchone()
        cursor.close()

        if student is None:
            return jsonify({"error": "Student not found"}), 404

        student["marks"] = float(student["marks"])
        return jsonify(student)

    finally:
        connection.close()


# -------------------------------
# 9. Start the application
# -------------------------------

if __name__ == "__main__":
    try:
        setup_database()

        result = load_students()
        print("CSV import result:", result)

        print("Open the website at http://127.0.0.1:5000")
        app.run(debug=True)

    except (Error, OSError, ValueError) as error:
        print("Project error:", error)
        print("Check MySQL, database credentials, and students.csv.")