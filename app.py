import os
from flask import Flask, render_template
from dotenv import load_dotenv
from login import HubLogin
from student import StudentServices
from staff import StaffServices
from maintenance import MaintenanceServices
from db import get_connection, log_action

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")


@app.before_request
def sync_equipment_statuses():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE EquipmentInventory e
            JOIN Reservations r ON e.equipmentID = r.equipmentID
            SET e.equipmentStatus = 'In Use'
            WHERE r.reservationStatus = 'Active'
              AND r.startTime <= NOW()
              AND e.equipmentStatus = 'Reserved'
        """)
        # Auto-complete reservations whose end time has passed without the
        # student manually ending them - opens the FR-10 inspection ticket
        # exactly like a manual end_reservation would.
        cursor.execute("""
            SELECT reservationID, equipmentID FROM Reservations
            WHERE reservationStatus = 'Active' AND endTime <= NOW()
        """)
        overdue = cursor.fetchall()

        for reservation_id, equipment_id in overdue:
            cursor.execute("""
                UPDATE Reservations SET reservationStatus = 'Completed'
                WHERE reservationID = %s
            """, (reservation_id,))

            cursor.execute("""
                INSERT INTO ActiveMaintenanceTickets
                    (reservationID, equipmentID, userID, ticketStatus, startTime)
                VALUES (%s, %s, NULL, 'Open', NOW())
            """, (reservation_id, equipment_id))

            cursor.execute("""
                UPDATE EquipmentInventory SET equipmentStatus = 'Maintenance'
                WHERE equipmentID = %s
            """, (equipment_id,))

            log_action(cursor, None, f"Auto-completed reservation #{reservation_id} (time expired)")

        conn.commit()
        cursor.close()
    finally:
        conn.close()


# ---------- Core ----------

@app.route("/")
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    return HubLogin.login()

@app.route('/logout')
def logout():
    return HubLogin.logout()


# ---------- Student ----------

@app.route('/student_dashboard')
def student_dashboard():
    return StudentServices.dashboard()

@app.route('/student_reservations', methods=['GET'])
def show_reservation_form():
    return StudentServices.show_reservation_form()

@app.route('/reservations/new', methods=['POST'])
def submit_reservation():
    return StudentServices.submit_reservation()

@app.route('/student_management', methods=['GET'])
def manage_reservations():
    return StudentServices.manage_reservations()

@app.route('/reservations/<id>/cancel', methods=['POST'])
def cancel_reservation(id):
    return StudentServices.cancel_reservation(id)

@app.route('/reservations/<id>/end', methods=['POST'])
def end_reservation(id):
    return StudentServices.end_reservation(id)


# ---------- Staff ----------

@app.route('/staff_dashboard')
def staff_dashboard():
    return StaffServices.dashboard()

@app.route('/staff/tickets/<equipment_id>')
def staff_ticket_history(equipment_id):
    return StaffServices.ticket_history(equipment_id)

@app.route('/staff/admin', methods=['GET'])
def staff_admin_tools():
    return StaffServices.admin_tools()

@app.route('/staff/reservations/<reservation_id>/update', methods=['POST'])
def staff_update_reservation(reservation_id):
    return StaffServices.update_reservation(reservation_id)

@app.route('/staff/reservations/<reservation_id>/cancel', methods=['POST'])
def staff_cancel_reservation(reservation_id):
    return StaffServices.cancel_reservation(reservation_id)

@app.route('/staff/consumables/<consumable_id>/adjust', methods=['POST'])
def staff_adjust_consumable(consumable_id):
    return StaffServices.adjust_consumable(consumable_id)


# ---------- Maintenance ----------

@app.route('/maintenance_dashboard')
def maintenance_dashboard():
    return MaintenanceServices.dashboard()

@app.route('/maintenance/tickets/<ticket_id>/claim', methods=['POST'])
def claim_ticket(ticket_id):
    return MaintenanceServices.claim_ticket(ticket_id)

@app.route('/maintenance/tickets/<ticket_id>/close', methods=['POST'])
def close_ticket(ticket_id):
    return MaintenanceServices.close_ticket(ticket_id)

@app.route('/maintenance/tickets/<ticket_id>/cancel', methods=['POST'])
def cancel_ticket(ticket_id):
    return MaintenanceServices.cancel_ticket(ticket_id)

@app.route('/maintenance/equipment/<equipment_id>/history')
def equipment_history(equipment_id):
    return MaintenanceServices.equipment_history(equipment_id)

@app.route('/maintenance/equipment', methods=['GET'])
def maintenance_equipment_page():
    return MaintenanceServices.equipment_page()

@app.route('/maintenance/equipment/new', methods=['POST'])
def add_equipment():
    return MaintenanceServices.add_equipment()

@app.route('/maintenance/equipment/<equipment_id>/status', methods=['POST'])
def update_equipment_status(equipment_id):
    return MaintenanceServices.update_equipment_status(equipment_id)


if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")