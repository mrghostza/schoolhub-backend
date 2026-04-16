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
    
    # Create a table for users
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL, 
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL
    )
    ''')

    # Create a table for notices (With Target Audience)
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
    
    # Smart Upgrade: Adds the target column if your database was made before this feature
    try:
        cursor.execute("ALTER TABLE notices ADD COLUMN target TEXT NOT NULL DEFAULT 'All'")
        conn.commit()
    except:
        pass # Column already exists!
    
    # Insert Dummy Data
    try:
        cursor.execute(
            "INSERT INTO users (role, username, password, name) VALUES (?, ?, ?, ?)", 
            ('admin', 'ADMIN-01', 'adminpass', 'Principal')
        )
        cursor.execute(
            "INSERT INTO users (role, username, password, name) VALUES (?, ?, ?, ?)", 
            ('teacher', 'EMP-012', 'teach123', 'Mr. Smith')
        )
        cursor.execute(
            "INSERT INTO users (role, username, password, name) VALUES (?, ?, ?, ?)", 
            ('student', 'STU-2026-045', '15042010', 'Zeeshan')
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Dummy data already exists
        
    conn.close()

# --- 2. FastAPI Setup ---
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

# --- 4. The Login Route ---
@app.post("/login")
def login(request: LoginRequest):
    conn = sqlite3.connect('schoolhub.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, role, name FROM users WHERE username=? AND password=?", 
        (request.username, request.password)
    )
    user = cursor.fetchone()
    conn.close()
    
    if user:
        user_id, role, name = user
        return {
            "success": True, 
            "message": "Login successful!", 
            "user_data": {
                "id": user_id, 
                "role": role, 
                "name": name
            }
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Incorrect username or password"
        )

# --- 5. The Live Stats Route ---
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
        
        return {
            "success": True, 
            "total_students": total_students, 
            "total_staff": total_staff, 
            "pending_leaves": 0, 
            "active_events": 1
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- 6. The Add User Route ---
@app.post("/admin/add_user")
def add_user(request: AddUserRequest):
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)", 
            (request.username, request.password, request.role, request.name)
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "message": f"Successfully added {request.name}!"}
        
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Error: This Admission No/ID already exists!"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- 7. The Broadcast Notice Route ---
@app.post("/admin/notice")
def broadcast_notice(request: NoticeRequest):
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        
        # Format the current date and time
        date_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
        
        cursor.execute(
            "INSERT INTO notices (title, message, date, author, target) VALUES (?, ?, ?, ?, ?)", 
            (request.title, request.message, date_str, request.author, request.target)
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "Notice broadcasted successfully!"}
        
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- 8. The Get Notices Route ---
@app.get("/notices")
def get_notices():
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()
        
        # Order by ID descending so the newest notices show up first!
        cursor.execute("SELECT id, title, message, date, author, target FROM notices ORDER BY id DESC")
        notices = cursor.fetchall()
        conn.close()
        
        notice_list = []
        for n in notices:
            notice_list.append({
                "id": n[0], 
                "title": n[1], 
                "message": n[2], 
                "date": n[3], 
                "author": n[4], 
                "target": n[5]
            })
            
        return {"success": True, "notices": notice_list}
        
    except Exception as e:
        return {"success": False, "message": str(e), "notices": []}

# --- 9. Run the Server ---
if __name__ == "__main__":
    print("Starting SchoolHub Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)