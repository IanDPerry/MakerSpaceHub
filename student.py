from flask import render_template, redirect, request, session
from db import get_connection, log_action


class StudentServices:

    # ---------- Dashboard ----------

    @staticmethod
    def dashboard():
        user_id = session.get('userID')
        if not user_id:
            return redirect('/')

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT
                    reservationID AS id,
                    CASE
                        WHEN reservationStatus = 'Active' AND startTime > NOW() THEN 'Upcoming'
                        WHEN reservationStatus = 'Active' AND startTime <= NOW() THEN 'Active'
                        ELSE reservationStatus
                    END AS status
                FROM Reservations
                WHERE userID = %s
                ORDER BY startTime DESC
            """, (user_id,))
            reservations = cursor.fetchall()

            cursor.execute("""
                SELECT CONCAT(manufacturer, ' ', model, ' is under maintenance') AS message
                FROM EquipmentInventory
                WHERE equipmentStatus = 'Maintenance'
            """)
            alerts = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return render_template('student_dashboard.html', reservations=reservations, alerts=alerts)

    # ---------- Request Reservation ----------

    @staticmethod
    def show_reservation_form():
        if not session.get('userID'):
            return redirect('/')

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT equipmentID AS id, CONCAT(manufacturer, ' | ', model) AS name
                FROM EquipmentInventory
                WHERE equipmentStatus = 'Available'
            """)
            available_equipment = cursor.fetchall()

            cursor.execute("""
                SELECT consumableID AS id, CONCAT(manufacturer, ' | ', model) AS name
                FROM ConsumableInventory
                WHERE count > 0
            """)
            available_consumables = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return render_template('student_reservations.html',
                                available_equipment=available_equipment,
                                available_consumables=available_consumables)

    @staticmethod
    def submit_reservation():
        user_id = session.get('userID')
        if not user_id:
            return redirect('/')

        equipment_ids = request.form.getlist('equipment')
        consumable_ids = request.form.getlist('consumables')
        start = request.form.get('start')
        end = request.form.get('end')

        if not equipment_ids or not start or not end:
            return "Equipment and a start/end time are required", 400
        if start >= end:
            return "End time must be after start time", 400

        conn = get_connection()
        try:
            cursor = conn.cursor()
            consumable_id = consumable_ids[0] if consumable_ids else None

            # FR-15: reject if any selected equipment already has an active
            # reservation overlapping the requested window
            for equipment_id in equipment_ids:
                cursor.execute("""
                    SELECT 1 FROM Reservations
                    WHERE equipmentID = %s
                      AND reservationStatus = 'Active'
                      AND startTime < %s AND endTime > %s
                    LIMIT 1
                """, (equipment_id, end, start))
                if cursor.fetchone():
                    cursor.close()
                    return f"Equipment {equipment_id} is already booked for that time", 409

            for equipment_id in equipment_ids:
                cursor.execute("""
                    INSERT INTO Reservations
                        (equipmentID, consumableID, userID, date, startTime, endTime, reservationStatus)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Active')
                """, (equipment_id, consumable_id, user_id, start[:10], start, end))

                cursor.execute("""
                    UPDATE EquipmentInventory SET equipmentStatus = 'Reserved' WHERE equipmentID = %s
                """, (equipment_id,))

                log_action(cursor, user_id, f"Reserved equipment #{equipment_id} from {start} to {end}")

            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/student_management')

    # ---------- Manage Reservations ----------

    @staticmethod
    def manage_reservations():
        user_id = session.get('userID')
        if not user_id:
            return redirect('/')

        ending_id = request.args.get('end')

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT reservationID AS id
                FROM Reservations
                WHERE userID = %s AND reservationStatus = 'Active' AND startTime > NOW()
            """, (user_id,))
            future_reservations = cursor.fetchall()

            cursor.execute("""
                SELECT reservationID AS id
                FROM Reservations
                WHERE userID = %s AND reservationStatus = 'Active' AND startTime <= NOW()
            """, (user_id,))
            active_reservations = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return render_template('student_management.html',
                                future_reservations=future_reservations,
                                active_reservations=active_reservations,
                                ending_id=ending_id)

    @staticmethod
    def cancel_reservation(reservation_id):
        user_id = session.get('userID')
        if not user_id:
            return redirect('/')

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            # Ownership check: only the student who booked it can cancel it
            cursor.execute("""
                SELECT equipmentID FROM Reservations
                WHERE reservationID = %s AND userID = %s AND reservationStatus = 'Active'
            """, (reservation_id, user_id))
            row = cursor.fetchone()
            if not row:
                cursor.close()
                return "Reservation not found", 404

            cursor.execute("""
                UPDATE Reservations SET reservationStatus = 'Cancelled'
                WHERE reservationID = %s AND userID = %s
            """, (reservation_id, user_id))

            cursor.execute("""
                UPDATE EquipmentInventory SET equipmentStatus = 'Available' WHERE equipmentID = %s
            """, (row['equipmentID'],))

            log_action(cursor, user_id, f"Cancelled reservation #{reservation_id}")

            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/student_management')

    @staticmethod
    def end_reservation(reservation_id):
        user_id = session.get('userID')
        if not user_id:
            return redirect('/')

        issue_type = request.form.get('issueType', 'none')

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT equipmentID FROM Reservations
                WHERE reservationID = %s AND userID = %s
            """, (reservation_id, user_id))
            row = cursor.fetchone()
            if not row:
                cursor.close()
                return "Reservation not found", 404
            equipment_id = row[0]

            cursor.execute("""
                UPDATE Reservations SET reservationStatus = 'Completed' WHERE reservationID = %s
                """, (reservation_id,))

            log_action(cursor, user_id, f"Ended reservation #{reservation_id}; ticket opened for equipment #{equipment_id}")

            # FR-10: every use requires post-use inspection, so a ticket
            # always opens here - either carrying the student's reported
            # issue, or standing in as the routine inspection ticket when
            # issue_type is 'none'. userID (technician) stays NULL until
            # claimed in maintenance.py.
            cursor.execute("""
                INSERT INTO ActiveMaintenanceTickets
                    (reservationID, equipmentID, userID, ticketStatus, startTime)
                VALUES (%s, %s, NULL, 'Open', NOW())
            """, (reservation_id, equipment_id))

            cursor.execute("""
                UPDATE EquipmentInventory SET equipmentStatus = 'Maintenance' WHERE equipmentID = %s
            """, (equipment_id,))

            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/student_management')