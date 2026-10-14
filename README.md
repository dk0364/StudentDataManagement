# Student Data Management System

A Python project that imports student records from CSV
into MySQL using Pandas and Flask.

## Features

- Read student records from CSV
- Validate and clean student data
- Store records in MySQL
- Skip duplicate student IDs
- Search by name, department, or city
- Display records on a Flask web page
- Provide REST API endpoints

## Technologies Used

- Python
- Pandas
- MySQL
- Flask
- HTML and CSS

## Installation

1. Install Python and MySQL Server.
2. Create and activate a Python virtual environment.
3. Install dependencies:

   pip install -r requirements.txt

4. Configure your MySQL username and password.
5. Put students.csv in the project folder.
6. Run the application:

   python app.py

7. Open http://127.0.0.1:5000 in your browser.

## API Endpoints

- GET /api/students
- GET /api/students?q=Hyderabad
- GET /api/students/1001

## Database

The application creates the student_db database
and students table if they do not already exist.