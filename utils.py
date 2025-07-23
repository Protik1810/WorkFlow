# Copyright (C) 2025 Protik Das
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License 
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import sys
import os
import sqlite3
import datetime
import json
import hashlib
from pathlib import Path
from tkinter import messagebox


from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QBuffer, QIODevice

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(os.path.abspath("."))
    return str(base_path / relative_path)

def get_app_config_base_path():
    """ Returns the base path to the config directory in a user-writable, cross-platform location. """
    app_name = "WorkflowApp"
    app_data_dir = Path.home() / "Documents" / app_name
    app_data_dir.mkdir(parents=True, exist_ok=True)
    return app_data_dir

def get_app_config_path():
    """ Returns the full path to the config file (e.g., app_config.json). """
    return str(get_app_config_base_path() / "app_config.json")

def get_departments_database_path():
    """ Returns the fixed path to the separate departments database file. """
    return str(get_app_config_base_path() / "departments.db")

# --- NEW: User Database Path ---
def get_users_database_path():
    """ Returns the fixed path to the user database file. """
    return str(get_app_config_base_path() / "users.db")

# --- NEW: User Database Functions ---
def init_users_db(db_path):
    """Initializes/upgrades the users table in the SQLite database."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                user_photo BLOB,          -- Store user photo as binary
                background_image BLOB,    -- Store custom background as binary
                createdAt TEXT,
                updatedAt TEXT,
                full_name TEXT,           -- NEW COLUMN: Full Name
                email TEXT                -- NEW COLUMN: Email ID
            )''')
            conn.commit()

            # --- Add columns if they don't exist (for existing databases) ---
            cursor.execute("PRAGMA table_info(users)")
            existing_columns = [col[1] for col in cursor.fetchall()]

            if 'full_name' not in existing_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
            if 'email' not in existing_columns:
                cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
            
            conn.commit()

    except sqlite3.Error as e:
        print(f"Error initializing/upgrading users table: {e}")
        raise

def hash_password(password):
    """Hashes a password using SHA-256 for basic security."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def check_password(hashed_password, password):
    """Checks a password against its hash."""
    return hashed_password == hashlib.sha256(password.encode('utf-8')).hexdigest()

def add_user(db_path, username, password, user_photo_blob=None, background_image_blob=None, full_name=None, email=None): # MODIFIED: Added full_name, email
    """Adds a new user to the database."""
    hashed_pass = hash_password(password)
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # MODIFIED: Insert new columns
            cursor.execute("INSERT INTO users (username, password_hash, user_photo, background_image, full_name, email, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (username, hashed_pass, user_photo_blob, background_image_blob, full_name, email, timestamp, timestamp))
            conn.commit()
            return cursor.lastrowid # Return the new user's ID
    except sqlite3.IntegrityError:
        # Username already exists
        return None
    except sqlite3.Error as e:
        print(f"Error adding user: {e}")
        return False

def get_user_by_username(db_path, username):
    """Retrieves user data by username."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # MODIFIED: Select new columns
            cursor.execute("SELECT id, username, password_hash, user_photo, background_image, full_name, email FROM users WHERE username = ?", (username,))
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None
    except sqlite3.Error as e:
        print(f"Error retrieving user: {e}")
        return None
    
def update_user_details(db_path, user_id, new_username, new_full_name, new_email):
    """Updates a user's username, full name, and email in the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("""
                UPDATE users 
                SET username = ?, full_name = ?, email = ?, updatedAt = ?
                WHERE id = ?
            """, (new_username, new_full_name, new_email, timestamp, user_id))
            conn.commit()
            return True # Indicates success
    except sqlite3.IntegrityError:
        # This error occurs if the new_username already exists for another user.
        print(f"Error: Username '{new_username}' already exists.")
        return None # Indicates a username conflict
    except sqlite3.Error as e:
        print(f"Error updating user details: {e}")
        return False # Indicates a general database error

def update_user_profile_image(db_path, user_id, user_photo_blob=None):
    """Updates a user's profile photo."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("UPDATE users SET user_photo = ?, updatedAt = ? WHERE id = ?",
                           (user_photo_blob, timestamp, user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error updating user photo: {e}")
        return False

def update_user_background_image(db_path, user_id, background_image_blob=None):
    """Updates a user's custom background image."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("UPDATE users SET background_image = ?, updatedAt = ? WHERE id = ?",
                           (background_image_blob, timestamp, user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error updating user background: {e}")
        return False

def update_user_password(db_path, user_id, new_password):
    """Updates a user's password in the database."""
    hashed_pass = hash_password(new_password)
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("UPDATE users SET password_hash = ?, updatedAt = ? WHERE id = ?",
                           (hashed_pass, timestamp, user_id))
            conn.commit()
            return cursor.rowcount > 0 # True if updated, False otherwise
    except sqlite3.Error as e:
        print(f"Error updating user password: {e}")
        return False

# --- Image to/from BLOB conversion functions ---
def image_to_blob(image_path):
    """Converts an image file at given path to a BLOB (bytes) suitable for SQLite."""
    try:
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            print(f"Warning: Could not load image from {image_path}")
            return None
        
        # Convert QPixmap to QImage first (often more reliable for format conversion)
        image = pixmap.toImage()
        
        byte_array = QBuffer()
        byte_array.open(QIODevice.OpenModeFlag.WriteOnly)
        
        # Save in a common format like PNG, which supports transparency if present.
        # Quality can be adjusted if needed (e.g., JPEG, but PNG is lossless).
        if not image.save(byte_array, "PNG"):
            print(f"Error: Failed to convert image {image_path} to PNG bytes.")
            return None
        
        return bytes(byte_array.data()) # Convert QByteArray to Python bytes
    except Exception as e:
        print(f"Error converting image to blob: {e}")
        return None

def qpixmap_to_blob(qpixmap):
    """Converts a QPixmap object to a BLOB (bytes) suitable for SQLite."""
    # --- ADD THIS CHECK ---
    if qpixmap is None:
        return None
    # --- END OF ADDITION ---
    if qpixmap.isNull():
        return None
    image = qpixmap.toImage()
    byte_array = QBuffer()
    byte_array.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(byte_array, "PNG"):
        return None
    return bytes(byte_array.data()) # Convert QByteArray to Python bytes

def blob_to_qpixmap(blob):
    """Converts a BLOB (bytes) from SQLite back to a QPixmap."""
    if blob is None:
        return QPixmap() # Return an empty pixmap
    try:
        pixmap = QPixmap()
        pixmap.loadFromData(blob, "PNG") # Assume PNG format for loading
        return pixmap
    except Exception as e:
        print(f"Error converting blob to QPixmap: {e}")
        return QPixmap() # Return empty pixmap on error

def init_departments_db(db_path):
    """Initializes the departments table in the SQLite database."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                address TEXT,
                createdAt TEXT,
                updatedAt TEXT
            )''')
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error initializing departments table: {e}")
        raise

def add_department_to_db(db_path, name, address):
    """Adds a new department to the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("INSERT INTO departments (name, address, createdAt, updatedAt) VALUES (?, ?, ?, ?)",
                           (name, address, timestamp, timestamp))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    except sqlite3.Error as e:
        print(f"Error adding department: {e}")
        return None

def get_all_departments_from_db(db_path):
    """Retrieves all departments from the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, address FROM departments ORDER BY name COLLATE NOCASE")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Error getting departments: {e}")
        return []

def get_department_by_id(db_path, dept_id):
    """Retrieves a single department by its ID from the database."""
    if dept_id is None: return None
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, address FROM departments WHERE id = ?", (dept_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"Error getting department by ID {dept_id}: {e}")
        return None

def update_department_in_db(db_path, dept_id, new_name, new_address):
    """Updates an existing department's details."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("UPDATE departments SET name = ?, address = ?, updatedAt = ? WHERE id = ?",
                           (new_name, new_address, timestamp, dept_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    except sqlite3.Error as e:
        print(f"Error updating department: {e}")
        return False

def delete_department_from_db(departments_db_path, projects_db_path, dept_id):
    """Deletes a department, checking for linked projects first."""
    try:
        with sqlite3.connect(projects_db_path) as projects_conn:
            projects_cursor = projects_conn.cursor()
            projects_cursor.execute("SELECT COUNT(*) FROM projects WHERE departmentId = ?", (dept_id,))
            if projects_cursor.fetchone()[0] > 0:
                # This dependency on tkinter.messagebox is the only UI call here.
                # In a pure backend, this would return an error code or raise an exception.
                # For this project, it's acceptable.
                messagebox.showerror("Deletion Error", "Cannot delete department. It is still linked to one or more projects.")
                return False

        with sqlite3.connect(departments_db_path) as departments_conn:
            departments_cursor = departments_conn.cursor()
            departments_cursor.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
            departments_conn.commit()
            return departments_cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Error deleting department: {e}")
        return False

def convert_number_to_words(number):
    # This function is purely computational and remains unchanged.
    if not isinstance(number, (int, float)): return "Invalid Number"
    if number < 0: return "Minus " + convert_number_to_words(abs(number))
    if number == 0: return "Zero Rupees Only"
    
    num_str = f"{number:.2f}"
    integer_part_str, decimal_part_str = num_str.split('.')
    rupees = int(integer_part_str)
    paise = int(decimal_part_str)

    def to_words(n):
        if n == 0: return ""
        units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
        words = ""
        if n < 20: words = units[n]
        elif n < 100: words = tens[n // 10] + (" " + units[n % 10] if n % 10 != 0 else "")
        elif n < 1000: words = units[n // 100] + " Hundred" + (" and " + to_words(n % 100) if n % 100 != 0 else "")
        elif n < 100000: words = to_words(n // 1000) + " Thousand" + (" " + to_words(n % 1000) if n % 1000 != 0 else "")
        elif n < 10000000: words = to_words(n // 100000) + " Lakh" + (" " + to_words(n % 100000) if n % 100000 != 0 else "")
        else: words = to_words(n // 10000000) + " Crore" + (" " + to_words(n % 10000000) if n % 10000000 != 0 else "")
        return words.strip()

    rupees_words = to_words(rupees).strip() if rupees > 0 else "Zero"
    final_words = f"Rupees {rupees_words}"
    if paise > 0:
        paise_words = to_words(paise).strip()
        final_words += f" and Paise {paise_words}"
    return final_words.strip() + " Only"

def log_activity(message, project_id=None):
    """Appends a structured log entry (JSON) to the activity log."""
    log_file_path = get_app_config_base_path() / "activity_log.json"
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    log_entry = {
        "timestamp": timestamp,
        "message": message,
        "project_id": project_id
    }
    
    try:
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f"Failed to write to activity log: {e}")
