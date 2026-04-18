from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import psycopg2
from psycopg2 import IntegrityError
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime

# --- YOUR IMMORTAL NEON DATABASE URL ---
DB_URL = "postgresql://neondb_owner:npg_q40SpTvBOsNL@ep-dry-queen-a1959t2i.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

def get_db_connection():
    return psycopg2.connect(DB_URL)

# --- 1. Database Setup ---
def setup_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # PostgreSQL uses SERIAL instead of AUTOINCREMENT
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, role TEXT NOT NULL, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, name TEXT NOT NULL, class_name TEXT NOT NULL DEFAULT 'N/A')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS notices (id SERIAL PRIMARY KEY, title TEXT NOT NULL, message TEXT NOT NULL, date TEXT NOT NULL, author TEXT NOT NULL, target TEXT NOT NULL DEFAULT 'All')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (id SERIAL PRIMARY KEY, student_username TEXT NOT NULL, date TEXT NOT NULL, status TEXT NOT NULL)''')
    
    # Safely add columns if they don't exist yet
    try: 
        cursor.execute("ALTER TABLE notices ADD COLUMN target TEXT NOT NULL DEFAULT 'All'")
        conn.commit()
    except Exception: 
        conn.rollback()
    
    try: 
        cursor.execute("ALTER TABLE users ADD COLUMN class_name TEXT NOT NULL DEFAULT 'N/A'")
        conn.commit()
    except Exception: 
        conn.rollback()

    # Insert Dummy Data (PostgreSQL uses %s instead of ?)
    try:
        cursor.execute("INSERT INTO users (role, username, password, name, class_name) VALUES (%s, %s, %s, %s, %s)", ('admin', 'ADMIN-01', 'adminpass', 'Principal', 'Admin'))
        cursor.execute("INSERT INTO users (role, username, password, name, class_name) VALUES (%s, %s, %s, %s, %s)", ('teacher', 'EMP-012', 'teach123', 'Mr. Smith', 'Faculty'))
        cursor.execute("INSERT INTO users (role, username, password, name, class_name) VALUES (%s, %s, %s, %s, %s)", ('student', 'STU-2026-045', '15042010', 'Alex Johnson', '11A'))
        cursor.execute("INSERT INTO users (role, username, password, name, class_name) VALUES (%s, %s, %s, %s, %s)", ('student', 'STU-2026-046', 'pass123', 'Mirza Mahreen', '11A'))
        cursor.execute("INSERT INTO users (role, username, password, name, class_name) VALUES (%s, %s, %s, %s, %s)", ('student', 'STU-2026-047', 'pass123', 'Junaid Ahmed', '10B'))
        cursor.execute("INSERT INTO users (role, username, password, name, class_name) VALUES (%s, %s, %s, %s, %s)", ('student', 'STU-2026-048', 'pass123', 'Dewan Sadiya', '9C'))
        conn.commit()
    except IntegrityError: 
        conn.rollback()
    
    # Permanent Welcome Notice
    cursor.execute("SELECT COUNT(*) FROM notices")
    if cursor.fetchone()[0] == 0:
        date_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
        cursor.execute("INSERT INTO notices (title, message, date, author, target) VALUES (%s, %s, %s, %s, %s)", ("Welcome to SchoolHub", "System verified. Connected to Neon Cloud Database.", date_str, "System Admin", "All"))
        conn.commit()
    
    cursor.close()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield

app = FastAPI(title="SchoolHub API", lifespan=lifespan)

class LoginRequest(BaseModel): username: str; password: str; role: str
class AddUserRequest(BaseModel): username: str; password: str; role: str; name: str
class NoticeRequest(BaseModel): title: str; message: str; author: str; target: str
class AttendanceRecord(BaseModel): student_username: str; date: str; status: str
class AttendanceBatchRequest(BaseModel): records: list[AttendanceRecord]

# --- NEW: UptimeRobot Ping Route ---
@app.get("/")
def ping_server():
    return {"status": "Alive and kicking!", "database": "Connected to Neon"}

@app.post("/login")
def login(request: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.role == 'student':
        cursor.execute("SELECT id, role, name FROM users WHERE username=%s AND password=%s AND role='student'", (request.username, request.password))
    else:
        cursor.execute("SELECT id, role, name FROM users WHERE username=%s AND password=%s AND role IN ('admin', 'teacher')", (request.username, request.password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user: return {"success": True, "message": "Login successful!", "user_data": {"id": user[0], "role": user[1], "name": user[2]}}
    else: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials or wrong role selected.")

@app.get("/admin/stats")
async def get_admin_stats():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        total_students = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE role IN ('admin', 'teacher')")
        total_staff = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return {"success": True, "total_students": total_students, "total_staff": total_staff, "pending_leaves": 0, "active_events": 1}
    except Exception as e: return {"success": False, "message": str(e)}

@app.post("/admin/add_user")
def add_user(request: AddUserRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, role, name) VALUES (%s, %s, %s, %s)", (request.username, request.password, request.role, request.name))
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "message": f"Successfully added {request.name}!"}
    except IntegrityError: return {"success": False, "message": "Error: This ID already exists!"}
    except Exception as e: return {"success": False, "message": str(e)}

@app.post("/admin/notice")
def broadcast_notice(request: NoticeRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        date_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
        cursor.execute("INSERT INTO notices (title, message, date, author, target) VALUES (%s, %s, %s, %s, %s)", (request.title, request.message, date_str, request.author, request.target))
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "message": "Notice broadcasted successfully!"}
    except Exception as e: return {"success": False, "message": str(e)}

@app.get("/notices")
def get_notices():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, message, date, author, target FROM notices ORDER BY id DESC")
        notices = cursor.fetchall()
        cursor.close()
        conn.close()
        notice_list = []
        now = datetime.now()
        for n in notices:
            try:
                notice_time = datetime.strptime(n[3], "%d %b %Y, %I:%M %p")
                if (now - notice_time).total_seconds() <= 86400:
                    notice_list.append({"id": n[0], "title": n[1], "message": n[2], "date": n[3], "author": n[4], "target": n[5]})
            except Exception: notice_list.append({"id": n[0], "title": n[1], "message": n[2], "date": n[3], "author": n[4], "target": n[5]})
        return {"success": True, "notices": notice_list}
    except Exception as e: return {"success": False, "message": str(e), "notices": []}

@app.get("/students")
def get_students(class_name: str = "11A"):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, name FROM users WHERE role='student' AND class_name=%s", (class_name,))
        students = cursor.fetchall()
        cursor.close()
        conn.close()
        student_list = [{"username": s[0], "name": s[1]} for s in students]
        return {"success": True, "students": student_list}
    except Exception as e: return {"success": False, "message": str(e), "students": []}

@app.post("/attendance/mark")
def mark_attendance(request: AttendanceBatchRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        for record in request.records:
            cursor.execute("DELETE FROM attendance WHERE student_username=%s AND date=%s", (record.student_username, record.date))
            cursor.execute("INSERT INTO attendance (student_username, date, status) VALUES (%s, %s, %s)", (record.student_username, record.date, record.status))
        conn.commit()
        cursor.close()
        conn.close()
        return {"success": True, "message": "Attendance saved successfully!"}
    except Exception as e: return {"success": False, "message": str(e)}

@app.get("/attendance")
def get_attendance():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT student_username, date, status FROM attendance")
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        record_list = [{"student_username": r[0], "date": r[1], "status": r[2]} for r in records]
        return {"success": True, "records": record_list}
    except Exception as e: return {"success": False, "message": str(e), "records": []}

@app.get("/student/attendance")
def get_student_attendance(username: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM attendance WHERE student_username=%s", (username,))
        records = cursor.fetchall()
        cursor.close()
        conn.close()
        total_classes = len(records)
        present_classes = sum(1 for r in records if r[0] == 'present')
        percentage = (present_classes / total_classes * 100) if total_classes > 0 else 0.0
        return {"success": True, "present_classes": present_classes, "total_classes": total_classes, "percentage": percentage}
    except Exception as e: return {"success": False, "message": str(e), "present_classes": 0, "total_classes": 0, "percentage": 0.0}

@app.get("/directory/{role}")
def get_directory(role: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, name, role, class_name FROM users WHERE role=%s", (role,))
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        user_list = [{"id": u[0], "username": u[1], "name": u[2], "role": u[3], "class_name": u[4]} for u in users]
        return {"success": True, "users": user_list}
    except Exception as e:
        return {"success": False, "message": str(e), "users": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)