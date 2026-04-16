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
        # Ignore error if dummy data already exists
        pass
        
    conn.close()

# --- 2. FastAPI Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs when the server starts
    setup_database()
    yield
    # This runs when the server shuts down

app = FastAPI(title="SchoolHub API", lifespan=lifespan)

# --- 3. Data Models (What the Android App will send) ---
class LoginRequest(BaseModel):
    username: str
    password: str
    role: str # 'student' or 'staff'

# --- 4. The Login Route ---
@app.post("/login")
def login(request: LoginRequest):
    conn = sqlite3.connect('schoolhub.db')
    cursor = conn.cursor()
    
    # Query the database to see if the user exists
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
        # If no match is found, throw an error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

# --- 5. The Admin Stats Route ---
@app.get("/admin/stats")
async def get_admin_stats():
    try:
        conn = sqlite3.connect('schoolhub.db')
        cursor = conn.cursor()

        # 1. Count Total Students
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='student'")
        total_students = cursor.fetchone()[0]

        # 2. Count Total Staff (which includes teachers and admins right now)
        cursor.execute("SELECT COUNT(*) FROM users WHERE role='staff' OR role='admin' OR role='teacher'")
        total_staff = cursor.fetchone()[0]

        conn.close()

        # Send the numbers back to the app!
        return {
            "success": True,
            "total_students": total_students,
            "total_staff": total_staff,
            "pending_leaves": 0,  
            "active_events": 1    
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

# --- 6. Run the Server (Always goes at the absolute bottom!) ---
if __name__ == "__main__":
    print("Starting SchoolHub Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)