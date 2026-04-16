from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import sqlite3
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime

# --- 1. Database Setup ---
def setup_database():
    conn = sqlite3.connect('schoolhub.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL, 
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        class_assigned TEXT DEFAULT 'None'
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        date TEXT NOT NULL,
        author TEXT NOT NULL,
        target TEXT NOT NULL DEFAULT 'All'
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_username TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL
    )
    ''')
    
    # Smart Upgrades for existing databases!
    try:
        cursor.execute("ALTER TABLE notices ADD COLUMN target TEXT NOT NULL DEFAULT 'All'")
    except: pass 
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN class_assigned TEXT DEFAULT 'None'")
    except: pass

    # Smart Patch: Put your test accounts into Class 11A so they can see each other!
    try:
        cursor.execute("UPDATE users SET class_assigned='Class 11A' WHERE username='EMP-012'")
        cursor.execute("UPDATE users SET class_assigned='Class 11A' WHERE username='STU-2026-045'")
    except: pass
    
    try:
        cursor.execute("INSERT INTO users (role, username, password, name, class_assigned) VALUES (?, ?, ?, ?, ?)", ('admin', 'ADMIN-01', 'adminpass', 'Principal', 'None'))
        cursor.execute("INSERT INTO users (role, username, password, name, class_assigned) VALUES (?, ?, ?, ?, ?)", ('teacher', 'EMP-012', 'teach123', 'Mr. Smith', 'Class 11A'))
        cursor.execute("INSERT INTO users (role, username, password, name, class_assigned) VALUES (?, ?, ?, ?, ?)", ('student', 'STU-2026-045', '15042010', 'Zeeshan', 'Class 11A'))
        # Adding a fake student in another class to prove filtering works!
        cursor.execute("INSERT INTO users (role, username, password, name, class_assigned) VALUES (?, ?, ?, ?, ?)", ('student', 'STU-002', '1234', 'Emily Peterson', 'Class 11A'))
        cursor.execute("INSERT INTO users (role, username, password, name, class_assigned) VALUES (?, ?, ?, ?, ?)", ('student', 'STU-003', '1234', 'Lucas Johnson', 'Class 10B'))
        conn.commit()
    except sqlite3.IntegrityError:
        pass 
        
    conn.commit()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_database()
    yield

app = FastAPI(title="SchoolHub API", lifespan=lifespan)

# --- 3. Data Models ---
class LoginRequest(BaseModel):
    username: str
    password: str
    role: str

class AddUserRequest(BaseModel):
    username: str
    password: str
    role: str
    name: str

class NoticeRequest(BaseModel):
    title: str
    message: str
    author: str
    target: str

class AttendanceRecord(BaseModel):
    student_username: str
    date: str
    status: str

class AttendanceBatchRequest(BaseModel):
    records: list[AttendanceRecord]

# --- ROUTES ---
@app.post("/login")
def login(request: LoginRequest):
    conn = sqlite3.connect('schoolhub.db')
    cursor = conn.cursor()
    # Now fetches class_assigned too!
    cursor.execute("SELECT id, role, name, class_assigned FROM users WHERE username=? AND password=?", (request.username, request.password))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {"success": True, "message": "Login successful!", "user_data": {"id": user[0], "role": user[1], "name": user[2], "class_assigned": user[3]}}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

@app.get("/admin/stats")
async def get_admin_stats():
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        total_students = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='staff' OR role='admin' OR role='teacher'")
        total_staff = cursor.fetchone()[0]
        conn.close()
        return {"success": True, "total_students": total_students, "total_staff": total_staff, "pending_leaves": 0, "active_events": 1}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/admin/add_user")
def add_user(request: AddUserRequest):
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)", (request.username, request.password, request.role, request.name))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Successfully added {request.name}!"}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Error: This Admission No/ID already exists!"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/admin/notice")
def broadcast_notice(request: NoticeRequest):
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        date_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
        cursor.execute("INSERT INTO notices (title, message, date, author, target) VALUES (?, ?, ?, ?, ?)", (request.title, request.message, date_str, request.author, request.target))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Notice broadcasted successfully!"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/notices")
def get_notices():
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, message, date, author, target FROM notices ORDER BY id DESC")
        notices = cursor.fetchall()
        conn.close()
        notice_list = [{"id": n[0], "title": n[1], "message": n[2], "date": n[3], "author": n[4], "target": n[5]} for n in notices]
        return {"success": True, "notices": notice_list}
    except Exception as e:
        return {"success": False, "message": str(e), "notices": []}

# --- ATTENDANCE ROUTES ---
@app.get("/students")
def get_students(class_name: str): # NEW: Requires a specific class!
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username, name FROM users WHERE role='student' AND class_assigned=?", (class_name,))
        students = cursor.fetchall()
        conn.close()
        student_list = [{"username": s[0], "name": s[1]} for s in students]
        return {"success": True, "students": student_list}
    except Exception as e:
        return {"success": False, "message": str(e), "students": []}

@app.post("/attendance/mark")
def mark_attendance(request: AttendanceBatchRequest):
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        for record in request.records:
            cursor.execute("DELETE FROM attendance WHERE student_username=? AND date=?", (record.student_username, record.date))
            cursor.execute("INSERT INTO attendance (student_username, date, status) VALUES (?, ?, ?)", (record.student_username, record.date, record.status))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Attendance saved successfully!"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/attendance")
def get_attendance():
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        cursor.execute("SELECT student_username, date, status FROM attendance")
        records = cursor.fetchall()
        conn.close()
        record_list = [{"student_username": r[0], "date": r[1], "status": r[2]} for r in records]
        return {"success": True, "records": record_list}
    except Exception as e:
        return {"success": False, "message": str(e), "records": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)