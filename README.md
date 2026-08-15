# Makerspace Hub+

Makerspace Hub+ is a web-based makerspace management system designed to manage equipment reservations, equipment inventory, consumable inventory, maintenance tickets, and user access.

The system provides separate functionality for three primary user roles:

- Student
- Staff
- Maintenance

The application is built using Flask and Python on the backend, HTML5 and CSS on the frontend, and MySQL for persistent data storage.

---

## Features

### Student Portal

Students can:

- Log into the system securely
- Access a student dashboard
- View available equipment
- Create equipment reservations
- View their reservations
- Manage active reservations
- Cancel reservations
- View reservation information
- Interact with the makerspace inventory system

### Staff Portal

Staff members can:

- Access the staff dashboard
- View operational information
- Manage reservations
- View equipment inventory
- Manage consumable inventory
- Monitor equipment status
- View administrative information
- Monitor maintenance activity
- Perform staff-level administrative operations

### Maintenance Portal

Maintenance users can:

- Access the maintenance dashboard
- View maintenance tickets
- Manage equipment maintenance
- View equipment information
- Update equipment lifecycle status
- Process maintenance-related operations
- Return equipment to an available state after maintenance

---

# Technology Stack

## Front End

- HTML5
- CSS3
- Jinja2 Templates
- Browser-based interface

The frontend uses standard HTML and CSS. Flask's Jinja2 template engine is used to insert dynamic values into the HTML before the response is sent to the browser.

### Front-End Technologies

| Technology | Purpose |
|---|---|
| HTML5 | Page structure, forms, tables, and navigation |
| CSS3 | Layout, styling, spacing, colors, and responsive behavior |
| Jinja2 | Dynamic server-side template rendering |
| Browser | Renders the final HTML and CSS |

---

## Back End

- Python
- Flask
- MySQL
- mysql-connector-python
- Werkzeug Security
- python-dotenv

### Backend Modules

| File | Purpose |
|---|---|
| `app.py` | Main Flask application and application routing |
| `login.py` | Authentication, password verification, sessions, and role-based access |
| `student.py` | Student dashboard and reservation functionality |
| `staff.py` | Staff dashboard, administration, reservations, and inventory |
| `maintenance.py` | Maintenance dashboard, tickets, and equipment lifecycle functionality |
| `db.py` | Centralized database connection and shared database utilities |

---

# Project Structure

```text
MakerspaceHub/
│
├── MakerSpace_data/
│   ├── Credential_references/
│   │   └── credential_references.csv
│   │
│   ├── Accounts.csv
│   ├── Users.csv
│   ├── Roles.csv
│   ├── EquipmentInventory.csv
│   └── ConsumableInventory.csv
│
├── mysql_db_schema/
│   └── schema.sql
│
├── static/
│   └── style.css
│
├── templates/
│   ├── index.html
│   ├── maintenance_dashboard.html
│   ├── maintenance_equipment.html
│   ├── staff_admin.html
│   ├── staff_dashboard.html
│   ├── student_dashboard.html
│   ├── student_management.html
│   └── student_reservations.html
│
├── app.py
├── db.py
├── login.py
├── maintenance.py
├── staff.py
├── student.py
│
├── example.env
├── requirements.txt
└── .gitignore