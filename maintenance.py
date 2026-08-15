from flask import render_template, redirect, request, session
from db import get_connection

MAINTENANCE_ROLE_ID = 3  # confirmed against Roles table: 1=student, 2=staff, 3=maintenance

# Fixed lifecycle - no longer maintenance-editable
VALID_TRANSITIONS = { 'Maintenance': {'Available'},}

class MaintenanceServices:

    # ---------- Access control ----------

    @staticmethod
    def _require_maintenance():
        if not session.get('userID') or session.get('roleID') != MAINTENANCE_ROLE_ID:
            return redirect('/')
        return None

    @staticmethod
    def _log_action(cursor, user_id, action):
        # FR-17: append-only audit trail
        cursor.execute(
            "INSERT INTO AuditLogs (userID, action) VALUES (%s, %s)",
            (user_id, action)
        )

    
    # ---------- Dashboard (US-03: all tickets centralized) ----------

    @staticmethod
    def dashboard():
        guard = MaintenanceServices._require_maintenance()
        if guard:
            return guard

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT
                    t.ticketID AS id,
                    CONCAT(e.manufacturer, ' ', e.model) AS equipment,
                    t.equipmentID AS equipmentID,
                    t.ticketStatus AS status,
                    t.startTime AS submitted,
                    t.userID AS assignedTo
                FROM ActiveMaintenanceTickets t
                JOIN EquipmentInventory e ON t.equipmentID = e.equipmentID
                ORDER BY (t.userID IS NULL) DESC, t.startTime ASC
            """)
            tickets = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        unassigned_count = sum(1 for t in tickets if t['assignedTo'] is None)

        return render_template('maintenance_dashboard.html',
                                tickets=tickets,
                                unassigned_count=unassigned_count,
                                current_user_id=session.get('userID'))

    # ---------- Ticket workflow (FR-13) ----------

    @staticmethod
    def claim_ticket(ticket_id):
        guard = MaintenanceServices._require_maintenance()
        if guard:
            return guard

        user_id = session.get('userID')

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ActiveMaintenanceTickets
                SET userID = %s, ticketStatus = 'In Progress'
                WHERE ticketID = %s AND userID IS NULL
            """, (user_id, ticket_id))

            if cursor.rowcount == 0:
                cursor.close()
                return "Ticket not found or already claimed", 409

            MaintenanceServices._log_action(cursor, user_id, f"Claimed ticket #{ticket_id}")
            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/maintenance_dashboard')

    @staticmethod
    def close_ticket(ticket_id):
        guard = MaintenanceServices._require_maintenance()
        if guard:
            return guard

        user_id = session.get('userID')

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT reservationID, equipmentID, userID, startTime
                FROM ActiveMaintenanceTickets
                WHERE ticketID = %s
            """, (ticket_id,))
            ticket = cursor.fetchone()

            if not ticket:
                cursor.close()
                return "Ticket not found", 404
            if ticket['userID'] != user_id:
                cursor.close()
                return "Only the assigned technician can close this ticket", 403

            cursor.execute("""
                INSERT INTO MaintenanceTicketsLog
                    (reservationID, equipmentID, userID, ticketStatus, startTime, endTime)
                VALUES (%s, %s, %s, 'Closed', %s, NOW())
            """, (ticket['reservationID'], ticket['equipmentID'], user_id, ticket['startTime']))

            cursor.execute("DELETE FROM ActiveMaintenanceTickets WHERE ticketID = %s", (ticket_id,))

            # FR-14: repair complete -> equipment returns to Available
            cursor.execute("""
                UPDATE EquipmentInventory SET equipmentStatus = 'Available' WHERE equipmentID = %s
            """, (ticket['equipmentID'],))

            MaintenanceServices._log_action(cursor, user_id, f"Closed ticket #{ticket_id}")
            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/maintenance_dashboard')

    @staticmethod
    def cancel_ticket(ticket_id):
        guard = MaintenanceServices._require_maintenance()
        if guard:
            return guard

        user_id = session.get('userID')

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT reservationID, equipmentID, userID, startTime
                FROM ActiveMaintenanceTickets
                WHERE ticketID = %s
            """, (ticket_id,))
            ticket = cursor.fetchone()

            if not ticket:
                cursor.close()
                return "Ticket not found", 404

            cursor.execute("""
                INSERT INTO MaintenanceTicketsLog
                    (reservationID, equipmentID, userID, ticketStatus, startTime, endTime)
                VALUES (%s, %s, %s, 'Cancelled', %s, NOW())
            """, (ticket['reservationID'], ticket['equipmentID'], user_id, ticket['startTime']))

            cursor.execute("DELETE FROM ActiveMaintenanceTickets WHERE ticketID = %s", (ticket_id,))

            cursor.execute("""
                UPDATE EquipmentInventory SET equipmentStatus = 'Available' WHERE equipmentID = %s
            """, (ticket['equipmentID'],))

            MaintenanceServices._log_action(cursor, user_id, f"Cancelled ticket #{ticket_id}")
            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/maintenance_dashboard')

    # ---------- Equipment history (US-07) ----------

    @staticmethod
    def equipment_history(equipment_id):
        guard = MaintenanceServices._require_maintenance()
        if guard:
            return guard

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT reservationID AS id, userID, startTime, endTime, reservationStatus AS status
                FROM Reservations
                WHERE equipmentID = %s
                ORDER BY startTime DESC
                LIMIT 25
            """, (equipment_id,))
            reservations = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return render_template('maintenance_equipment_history.html',
                                reservations=reservations,
                                equipment_id=equipment_id)

    # ----------Admin tools----------

    @staticmethod
    def equipment_page():
        guard = MaintenanceServices._require_maintenance()
        if guard:
            return guard

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT
                    e.equipmentID AS id,
                    e.manufacturer,
                    e.model,
                    e.equipmentStatus AS status,
                    EXISTS(
                        SELECT 1 FROM ActiveMaintenanceTickets t
                        WHERE t.equipmentID = e.equipmentID
                    ) AS has_ticket
                FROM EquipmentInventory e
                ORDER BY e.manufacturer
                """)
            equipment = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return render_template('maintenance_equipment.html', equipment=equipment)

    @staticmethod
    def add_equipment():
        guard = MaintenanceServices._require_maintenance()
        if guard:
            return guard

        manufacturer = request.form.get('manufacturer')
        model = request.form.get('model')

        if not manufacturer or not model:
            return "Manufacturer and model are required", 400

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO EquipmentInventory (manufacturer, model, equipmentStatus)
                VALUES (%s, %s, 'Available')
            """, (manufacturer, model))

            MaintenanceServices._log_action(
                cursor, session.get('userID'), f"Added equipment: {manufacturer} {model}"
            )
            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/maintenance/equipment')

    @staticmethod
    def update_equipment_status(equipment_id):
        guard = MaintenanceServices._require_maintenance()
        if guard:
            return guard

        new_status = request.form.get('status')
        if new_status not in {'Available', 'Reserved', 'In Use', 'Maintenance'}:
            return "Invalid status", 400

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT equipmentStatus FROM EquipmentInventory WHERE equipmentID = %s
            """, (equipment_id,))
            row = cursor.fetchone()
            if not row:
                cursor.close()
                return "Equipment not found", 404

            current_status = row['equipmentStatus']

            current_status = row['equipmentStatus']
            if new_status not in VALID_TRANSITIONS.get(current_status, set()):
                cursor.close()
                return f"Cannot move equipment from {current_status} to {new_status}", 400

            cursor.execute("""
                UPDATE EquipmentInventory SET equipmentStatus = %s WHERE equipmentID = %s
            """, (new_status, equipment_id))

            MaintenanceServices._log_action(
                cursor, session.get('userID'),
                f"Updated equipment #{equipment_id} status: {current_status} -> {new_status}"
            )
            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/maintenance/equipment')

    