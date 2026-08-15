from flask import render_template, redirect, request, session
from db import get_connection, log_action

STAFF_ROLE_ID = 2  # confirmed against Roles table: 1=student, 2=staff, 3=maintenance


class StaffServices:

    # ---------- Access control ----------

    @staticmethod
    def _require_staff():
        if not session.get('userID') or session.get('roleID') != STAFF_ROLE_ID:
            return redirect('/')
        return None

    # ---------- Dashboard (FR-05, FR-06, FR-18) ----------

    @staticmethod
    def dashboard():
        guard = StaffServices._require_staff()
        if guard:
            return guard

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)

            # FR-18: active tickets table
            cursor.execute("""
                SELECT
                    t.ticketID AS id,
                    CONCAT(e.manufacturer, ' ', e.model) AS equipment,
                    t.ticketStatus AS status,
                    t.startTime AS submitted
                FROM ActiveMaintenanceTickets t
                JOIN EquipmentInventory e ON t.equipmentID = e.equipmentID
                ORDER BY t.startTime DESC
            """)
            tickets = cursor.fetchall()

            # ---- FR-05: operational metrics ----
            cursor.execute("""
                SELECT COUNT(*) AS count FROM Reservations
                WHERE reservationStatus = 'Active'
            """)
            active_reservations = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) AS count FROM Reservations
                WHERE startTime >= NOW() - INTERVAL 7 DAY
            """)
            reservation_volume_7d = cursor.fetchone()['count']

            cursor.execute("""
                SELECT ticketStatus AS status, COUNT(*) AS count
                FROM ActiveMaintenanceTickets
                GROUP BY ticketStatus
            """)
            ticket_activity = cursor.fetchall()
            open_tickets = next((r['count'] for r in ticket_activity if r['status'] == 'Open'), 0)

            # Live equipment status breakdown, so staff aren't blind to it
            cursor.execute("""
                SELECT equipmentStatus AS status, COUNT(*) AS count
                FROM EquipmentInventory
                GROUP BY equipmentStatus
            """)
            equipment_status_summary = cursor.fetchall()

            # ---- FR-06: KPIs ----

            # Equipment utilization rate: % of equipment currently reserved/in-use
            cursor.execute("SELECT COUNT(*) AS count FROM EquipmentInventory")
            total_equipment = cursor.fetchone()['count']

            cursor.execute("""
                SELECT COUNT(*) AS count FROM EquipmentInventory
                WHERE equipmentStatus IN ('Reserved', 'In Use')
            """)
            in_use_equipment = cursor.fetchone()['count']

            utilization_rate = (
                round(in_use_equipment / total_equipment * 100, 1) if total_equipment else 0
            )

            # Maintenance turnaround time (avg hours open -> closed), from the
            # log since closed tickets move out of ActiveMaintenanceTickets
            cursor.execute("""
                SELECT AVG(TIMESTAMPDIFF(HOUR, startTime, endTime)) AS avg_hours
                FROM MaintenanceTicketsLog
                WHERE ticketStatus = 'Closed'
            """)
            row = cursor.fetchone()
            avg_turnaround_hours = round(row['avg_hours'], 1) if row['avg_hours'] is not None else None

            # Inventory consumption trend stand-in: low-stock consumables
            # (a real trend needs usage-history/audit data per FR-17)
            cursor.execute("""
                SELECT consumableID AS id, CONCAT(manufacturer, ' ', model) AS name, count
                FROM ConsumableInventory
                WHERE count <= 5
                ORDER BY count ASC
            """)
            low_stock_consumables = cursor.fetchall()

            cursor.close()
        finally:
            conn.close()

        return render_template('staff_dashboard.html',
                                tickets=tickets,
                                active_reservations=active_reservations,
                                open_tickets=open_tickets,
                                reservation_volume_7d=reservation_volume_7d,
                                ticket_activity=ticket_activity,
                                equipment_status_summary=equipment_status_summary,
                                utilization_rate=utilization_rate,
                                avg_turnaround_hours=avg_turnaround_hours,
                                low_stock_consumables=low_stock_consumables)

    # ---------- Ticket tracking (FR-12) ----------

    @staticmethod
    def ticket_history(equipment_id):
        guard = StaffServices._require_staff()
        if guard:
            return guard

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT ticketID AS id, ticketStatus AS status, startTime, endTime, userID
                FROM ActiveMaintenanceTickets
                WHERE equipmentID = %s

                UNION ALL

                SELECT maintenanceLogID AS id, ticketStatus AS status, startTime, endTime, userID
                FROM MaintenanceTicketsLog
                WHERE equipmentID = %s

                ORDER BY startTime DESC
            """, (equipment_id, equipment_id))
            history = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return render_template('staff_ticket_history.html', history=history, equipment_id=equipment_id)

    # ----------Admin tools----------

    @staticmethod
    def admin_tools():
        guard = StaffServices._require_staff()
        if guard:
            return guard

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT reservationID AS id, equipmentID, userID, startTime, endTime, reservationStatus AS status
                FROM Reservations
                WHERE reservationStatus != 'Completed'
                ORDER BY startTime DESC
            """)
            reservations = cursor.fetchall()

            cursor.execute("""
                SELECT consumableID AS id, manufacturer, model, count
                FROM ConsumableInventory
                ORDER BY manufacturer
            """)
            consumables = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return render_template('staff_admin.html', reservations=reservations, consumables=consumables)

 # ---------- Reservation admin (FR-11) ----------
    @staticmethod
    def update_reservation(reservation_id):
        guard = StaffServices._require_staff()
        if guard:
            return guard

        new_status = request.form.get('status')
        if new_status not in {'Active', 'Cancelled', 'Completed'}:
            return "Invalid status", 400

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE Reservations SET reservationStatus = %s WHERE reservationID = %s
            """, (new_status, reservation_id))

            log_action(cursor, session.get('userID'), f"Updated reservation #{reservation_id} status to {new_status}")

            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/staff/admin')

    @staticmethod
    def cancel_reservation(reservation_id):
        # Staff can cancel any reservation (admin override) - unlike students,
        # who can only cancel their own (see StudentServices.cancel_reservation)
        guard = StaffServices._require_staff()
        if guard:
            return guard

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT equipmentID FROM Reservations WHERE reservationID = %s", (reservation_id,))
            row = cursor.fetchone()
            if not row:
                cursor.close()
                return "Reservation not found", 404

            cursor.execute("""
                UPDATE Reservations SET reservationStatus = 'Cancelled' WHERE reservationID = %s
            """, (reservation_id,))

            cursor.execute("""
                UPDATE EquipmentInventory SET equipmentStatus = 'Available' WHERE equipmentID = %s
            """, (row['equipmentID'],))

            log_action(cursor, session.get('userID'), f"Cancelled reservation #{reservation_id} (staff override)")

            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/staff/admin')

    # ---------- Consumable inventory admin (FR-11, FR-16) ----------

    @staticmethod
    def adjust_consumable(consumable_id):
        guard = StaffServices._require_staff()
        if guard:
            return guard

        try:
            delta = int(request.form.get('delta', ''))
        except ValueError:
            return "Adjustment must be a whole number", 400

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT count FROM ConsumableInventory WHERE consumableID = %s", (consumable_id,))
            row = cursor.fetchone()
            if not row:
                cursor.close()
                return "Consumable not found", 404

            new_count = row['count'] + delta
            if new_count < 0:  # FR-16 / DB CHECK constraint backs this up too
                cursor.close()
                return "Adjustment would drop inventory below zero", 400

            cursor.execute("""
                UPDATE ConsumableInventory SET count = %s WHERE consumableID = %s
            """, (new_count, consumable_id))

            log_action(cursor, session.get('userID'), f"Adjusted consumable #{consumable_id} by {delta}")
            
            conn.commit()
            cursor.close()
        finally:
            conn.close()

        return redirect('/staff/admin')