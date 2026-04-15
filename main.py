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
    # (Using plain text passwords for the MVP, but we'll encrypt these later)
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
        # In a real app, we'd return a secure JWT Token here. 
        # For now, we return a success message and their data!
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

# Run the server
if __name__ == "__main__":
    print("Starting SchoolHub Backend...")
    uvicorn.run(app, host="0.0.0.0", port=8000)