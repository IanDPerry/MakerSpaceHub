from flask import request, session, redirect
from werkzeug.security import check_password_hash
from db import get_connection


class HubLogin:

    # Map roleID -> landing page after login (confirmed against Roles table)
    ROLE_REDIRECTS = {
        1: '/student_dashboard',
        2: '/staff_dashboard',
        3: '/maintenance_dashboard',
    }

    @staticmethod
    def login():
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return "Username and password required", 400

        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT Users.userID, Users.roleID, Accounts.passwordHash
                FROM Accounts
                JOIN Users ON Accounts.userID = Users.userID
                WHERE Accounts.userName = %s
            """, (username,))
            account = cursor.fetchone()
            cursor.close()
        finally:
            conn.close()

        if not account or not check_password_hash(account['passwordHash'], password):
            return "Invalid username or password", 401

        session['userID'] = account['userID']
        session['roleID'] = account['roleID']

        redirect_url = HubLogin.ROLE_REDIRECTS.get(account['roleID'], '/')
        return redirect(redirect_url)

    @staticmethod
    def logout():
        session.clear()
        return redirect('/')