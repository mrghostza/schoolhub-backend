from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import sqlite3
import uvicorn
from contextlib import asynccontextmanager

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
    
    # Insert some dummy data for us to test with!
    try:
        cursor.execute("INSERT INTO users (role, username, password, name) VALUES ('admin', 'ADMIN-01', 'adminpass', 'Principal (Dad)')")
        cursor.execute("INSERT INTO users (role, username, password, name) VALUES ('teacher', 'EMP-012', 'teach123', 'Mr. Smith')")
        cursor.execute("INSERT INTO users (role, username, password, name) VALUES ('student', 'STU-2026-045', '15042010', 'Zeeshan')")
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Ignore error if dummy data already exists
        
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
            "user_data": {"id": user_id, "role": role, "name": name}
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

# --- 6. The Add User Route (The CMS) ---
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

# --- 7. Run the Server ---
if __name__ == "__main__":
    print("Starting SchoolHub Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)