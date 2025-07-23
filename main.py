# Copyright (C) 2025 Protik Das
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# This file marks the 'ui' directory as a Python package.
# It remains empty as no package-level initialization is required here.

import sys
import os
import sqlite3
import json
import uuid
import datetime
import copy
import re
import tempfile
import shutil
import zipfile
import darkdetect 
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QMessageBox,QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDialogButtonBox,
    QFileDialog, QMenuBar, QMenu, QProgressDialog, QStatusBar, QPushButton, QToolButton ,QGridLayout,
    QHBoxLayout,  QWidgetAction, QGraphicsDropShadowEffect, 
)
from PyQt6.QtGui import QIcon, QAction, QActionGroup, QPixmap, QPalette, QBrush, QPainter, QFont, QColor
from PyQt6.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal, QRectF

import utils
from config import (
    DEFAULT_ICON_PATH, DEFAULT_LOGO_PATH,
    SUBFOLDER_NAMES, initial_project_data_template
)
from ui.pages import (
    HomeView, NewProjectP1, NewProjectP2_Department,NewProjectP2A_Enquiry, NewProjectP3_OEM,
    NewProjectP4_ProposalOrder, NewProjectP4A_Scope, NewProjectP4B_BOM,
    NewProjectP5_OEN, TenderManagementPage, LimitedTenderView, ProjectDetailsView,
    FinancialDetailsView, ProjectCreationPreview, FulfillmentView,
    VendorPaymentView, AdminDepartmentView,
    UserProfileView,
    PageFrame
)
from ui.auth_dialog import LoginSignUpDialog

if getattr(sys, 'frozen', False):
    BASE_PATH = Path(sys._MEIPASS)
else:
    BASE_PATH = Path(__file__).parent.resolve()

APP_VERSION = "2.0.0"
DARK_THEMES = { "github_dark", "carbon_fiber_theme", "crimson_gold", "scifi_theme", "blueprint_theme", "charcoal_teal" }

class BackupWorker(QObject):
    finished = pyqtSignal(bool)
    progress = pyqtSignal(int)
    error = pyqtSignal(str)
    
    def __init__(self, working_folder, db_path, departments_db_path, is_manual=False):
        super().__init__()
        self.working_folder = working_folder; self.db_path = db_path
        self.departments_db_path = departments_db_path; self.is_manual = is_manual

    def run(self):
        try:
            backup_dir = utils.get_app_config_base_path() / "Global_Backups"; backup_dir.mkdir(exist_ok=True)
            working_folder_name = Path(self.working_folder).name
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = backup_dir / f"Backup_{working_folder_name}_{timestamp}.zip"
            files_to_backup = []
            if self.db_path.exists(): files_to_backup.append((self.db_path, f"{working_folder_name}/{self.db_path.name}"))
            if Path(self.departments_db_path).exists(): files_to_backup.append((Path(self.departments_db_path), Path(self.departments_db_path).name))
            
            for item in Path(self.working_folder).iterdir():
                if item.is_dir() and item.name != "backups":
                    for root, _, files in os.walk(item):
                        for file in files:
                            file_path = Path(root) / file; arcname = f"{working_folder_name}/{file_path.relative_to(self.working_folder)}"
                            files_to_backup.append((file_path, arcname))
            
            if not files_to_backup: self.finished.emit(True); return

            with zipfile.ZipFile(backup_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                total_files = len(files_to_backup)
                for i, (file_path, arcname) in enumerate(files_to_backup):
                    zipf.write(file_path, arcname); self.progress.emit(int(((i + 1) / total_files) * 100))
            
            all_backups = sorted(backup_dir.glob(f"Backup_{working_folder_name}_*.zip"), key=os.path.getmtime, reverse=True)
            for old_backup in all_backups[7:]: old_backup.unlink()
            
            utils.log_activity(f"Backup created for '{working_folder_name}'."); self.finished.emit(True)
        except Exception as e:
            self.error.emit(f"Could not create backup: {e}"); self.finished.emit(False)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About WORKFLOW")
        
        layout = QGridLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setColumnStretch(1, 1)

        # Column 0: Logo
        logo_label = QLabel()
        logo_path = utils.resource_path(DEFAULT_LOGO_PATH)
        if Path(logo_path).exists():
            pixmap = QPixmap(logo_path).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        layout.addWidget(logo_label, 0, 0, 4, 1, Qt.AlignmentFlag.AlignTop)

        # Column 1: Information
        title_label = QLabel(f"WORKFLOW v{APP_VERSION}")
        font = title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        title_label.setFont(font)

        description_label = QLabel("A desktop application for managing project workflows, from inception to fulfillment and financial tracking.")
        description_label.setWordWrap(True)

        # --- THIS IS THE FIX ---
        # Detect the current theme and choose a link color with good contrast.
        theme = darkdetect.theme()
        link_color = "#87FC32" if theme == "Dark" else "#62C0FF" # Light blue for dark, standard for light
        
        info_text = (
            "<p><b>Copyright &copy; 2025 Protik Das</b></p>"
            "<p>This program is distributed under the terms of the "
            f"<p><a style='color: {link_color};'href='https://www.gnu.org/licenses/gpl-3.0.html'>GNU General Public License v3.0</a>.</p>"
        )
        # --- END OF FIX ---
        info_label = QLabel(info_text)
        info_label.setOpenExternalLinks(True)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)

        layout.addWidget(title_label, 0, 1)
        layout.addWidget(description_label, 1, 1)
        layout.addWidget(info_label, 2, 1)
        layout.setRowStretch(3, 1) # Spacer to push button to the bottom
        layout.addWidget(button_box, 4, 1, Qt.AlignmentFlag.AlignRight)

        self.setFixedSize(540, 240)
# --- END OF NEW CLASS ---

class WorkflowApp(QMainWindow):
    def __init__(self, user_data=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle(f"WORKFLOW")
        self.setup_icon()
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(900, 700)
        self.setStatusBar(QStatusBar(self))
        
        self.config_data = {}
        self.current_project_data = None
        self.all_projects_data = []
        self.working_folder = ""
        self.db_path = None
        self.departments_db_path = utils.get_departments_database_path()
        self.users_db_path = utils.get_users_database_path()
        self.app_ready = False
        self.themes_path = BASE_PATH / "themes"
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        self.frames = {}
        self.page_classes = {
            cls.__name__: cls for cls in (
                HomeView, NewProjectP1, NewProjectP2_Department,NewProjectP2A_Enquiry, NewProjectP3_OEM,
                NewProjectP4_ProposalOrder, NewProjectP4A_Scope, NewProjectP4B_BOM,
                NewProjectP5_OEN, TenderManagementPage,LimitedTenderView, ProjectDetailsView,
                FinancialDetailsView, ProjectCreationPreview, FulfillmentView,
                VendorPaymentView, AdminDepartmentView,
                UserProfileView,
                PageFrame
            )
        }
        self.current_user_data = user_data
        
        self.load_config()
        self.create_menu_bar()
        
        if self.current_user_data:
            QTimer.singleShot(0, self.complete_initial_setup)
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        
        actions = [
            ("Select/Change Working Folder", self.select_working_folder_menu_action),
            ("Backup Current Folder...", self.handle_manual_backup),
            ("Restore from Backup...", self.restore_from_backup),
            ("Restart", self.restart_application),
            ("Home", self.handle_save_and_go_home),
        ]
        for text, callback in actions:
            file_menu.addAction(QAction(text, self, triggered=callback))

        file_menu.addSeparator()
        file_menu.addAction(QAction("Exit", self, triggered=self.close))

        settings_menu = menubar.addMenu("&Settings")
        self.themes_menu = settings_menu.addMenu("&Themes")
        
        dept_manager_menu = settings_menu.addMenu("&Department Manager")
        dept_manager_menu.addAction(QAction("Manage Departments", self, triggered=self.show_admin_login))

        self.user_profile_menu = QMenu(self)

        # 1. Create the widget and labels that will display user info.
        #    We create them once and will update their text later.
        user_info_widget = QWidget()
        layout = QVBoxLayout(user_info_widget)
        layout.setContentsMargins(10, 8, 10, 8)
        
        self.menu_username_label = QLabel("<b>Username</b>")
        self.menu_fullname_label = QLabel("Full Name")
        self.menu_email_label = QLabel("email@example.com")
        
        # Style the labels
        font = self.menu_fullname_label.font()
        font.setPointSize(9)
        self.menu_fullname_label.setFont(font)
        self.menu_email_label.setFont(font)
        self.menu_email_label.setStyleSheet("color: grey;")

        layout.addWidget(self.menu_username_label)
        layout.addWidget(self.menu_fullname_label)
        layout.addWidget(self.menu_email_label)
        
        # 2. Create the QWidgetAction and set our custom widget on it.
        user_info_action = QWidgetAction(self)
        user_info_action.setDefaultWidget(user_info_widget)
        
        # 3. Build the menu
        self.user_profile_menu.addAction(user_info_action)
        self.user_profile_menu.addSeparator()

        profile_action = QAction("User Profile", self, triggered=lambda: self.show_frame("UserProfileView"))
        lock_action = QAction("Lock Profile", self, triggered=self._lock_profile)
        logout_action = QAction("Logout", self, triggered=self.handle_logout)
        
        self.user_profile_menu.addAction(profile_action)
        self.user_profile_menu.addAction(lock_action)
        self.user_profile_menu.addSeparator()
        self.user_profile_menu.addAction(logout_action)
        
        settings_menu.addMenu(self.user_profile_menu)

        menubar.addAction(QAction("About", self, triggered=self.show_about_dialog))

        right_corner_container = QWidget(menubar)
        right_corner_layout = QHBoxLayout(right_corner_container)
        right_corner_layout.setContentsMargins(0, 0, 0, 0)
        right_corner_layout.setSpacing(5)
        
        self.home_menubar_button = QPushButton(right_corner_container, objectName="HomeMenuBarButton")
        self.home_menubar_button.setFixedSize(30,30)
        self.home_menubar_button.setToolTip("Go to Home Page")
        self.home_menubar_button.clicked.connect(self.handle_save_and_go_home)
        right_corner_layout.addWidget(self.home_menubar_button)

        self.user_icon_menubar_button = QToolButton(right_corner_container, objectName="UserIconMenuBarButton")
        self.user_icon_menubar_button.setFixedSize(30, 30)
        self.user_icon_menubar_button.setMenu(self.user_profile_menu)
        self.user_icon_menubar_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.user_icon_menubar_button.setAutoRaise(True) # Makes the button flat and borderless
        self.user_icon_menubar_button.setArrowType(Qt.ArrowType.NoArrow)        
        right_corner_layout.addWidget(self.user_icon_menubar_button)
        
        menubar.setCornerWidget(right_corner_container, Qt.Corner.TopRightCorner)

    def _apply_shadow_to_menus(self):
        """Creates and applies a shadow effect to all menus in the menu bar."""
        # Find all QMenu objects in the menuBar
        for menu in self.menuBar().findChildren(QMenu):
            shadow = QGraphicsDropShadowEffect(self)
            # Making the shadow a bit more visible to ensure it's not just faint
            shadow.setBlurRadius(20)
            shadow.setOffset(2, 2)
            shadow.setColor(QColor(0, 0, 0, 90))

            menu.setGraphicsEffect(shadow)
            
            # This attribute allows for transparency, which is needed for the shadow.
            menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            # THIS IS THE CRITICAL FIX:
            # We remove the border AND add a margin. The margin creates the empty
            # space around the menu where the shadow will be drawn.
            menu.setStyleSheet("QMenu { border: none; margin: 8px; }")

    def _generate_initials_icon(self, username, size=24):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent) # Use a transparent background
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # CORRECTED: Get the text color from the current application theme's palette.
        # This is more reliable than checking filenames.
        text_color = QApplication.palette().color(QPalette.ColorRole.ButtonText)
        painter.setPen(text_color)
        
        font = QFont("Arial", int(size * 0.5), QFont.Weight.Bold)
        painter.setFont(font)
        
        initials = "".join([word[0].upper() for word in username.split() if word])[:2] or "?"
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, initials)
        painter.end()
        return QIcon(pixmap)

    def _update_user_profile_ui(self):
        if not hasattr(self, 'user_profile_menu') or not self.current_user_data: 
            return
        
        # --- Get latest user data ---
        username = self.current_user_data.get('username', 'User')
        full_name = self.current_user_data.get('full_name', '')
        email = self.current_user_data.get('email', '')
        
        # --- Update the menu bar button text and icon ---
        self.user_profile_menu.setTitle(username)
        self.user_icon_menubar_button.setToolTip(f"User options for {username}")
        
        user_photo_blob = self.current_user_data.get('user_photo')
        icon = self._generate_initials_icon(username, 30)
        if user_photo_blob:
            pixmap = utils.blob_to_qpixmap(user_photo_blob)
            if not pixmap.isNull():
                icon = QIcon(pixmap)
        
        self.user_icon_menubar_button.setIcon(icon)
        self.user_icon_menubar_button.setIconSize(self.user_icon_menubar_button.size() * 0.9)
        
        # --- Update the text of the labels within the menu dropdown ---
        self.menu_username_label.setText(f"<b>{username}</b>")
        self.menu_fullname_label.setText(full_name)
        self.menu_email_label.setText(email)
        
        # Only show the full name and email labels if they have content
        self.menu_fullname_label.setVisible(bool(full_name))
        self.menu_email_label.setVisible(bool(email))

    def _lock_profile(self):
        """
        Locks the application by hiding the main window and requiring re-authentication,
        while isolating it from the main application's theme and allowing minimization.
        """
        if not self.current_user_data:
            return

        # 1. Store the application's current theme
        current_stylesheet = QApplication.instance().styleSheet()
        
        # 2. Temporarily clear the global theme so the dialog can use its own style
        QApplication.instance().setStyleSheet("")
        
        # 3. Hide the main window to create the "locked" experience
        self.hide()

        login_prefs = self.config_data.get('login', {})
        username = login_prefs.get('username')
        should_remember = login_prefs.get('stay_logged_in') or login_prefs.get('remember_me')
        password = login_prefs.get('password') if should_remember else None
        
        if not username:
            username = self.current_user_data.get('username')

        # 4. Create the dialog without a parent
        lock_dialog = LoginSignUpDialog(
            parent=None,
            app_version=APP_VERSION,
            initial_username=username,
            initial_password=password
        )
        
        # 5. Connect the dialog's minimize request to the main window's minimize function
        lock_dialog.minimize_app_request.connect(self.showMinimized)
        
        # 6. Execute the dialog and store its result
        result = lock_dialog.exec()
        
        # 7. IMPORTANT: Restore the main application's theme immediately after the dialog closes
        QApplication.instance().setStyleSheet(current_stylesheet)
        
        # 8. Handle the result
        if result == QDialog.DialogCode.Accepted:
            # On success, show the main window again and bring it to the front
            self.show()
            self.raise_()
            self.activateWindow()
            self.statusBar().showMessage(f"Welcome back, {username}!", 3000)
        else:
            # On failure or cancel, quit the entire application
            QApplication.instance().quit()

    def handle_logout(self):
        if QMessageBox.question(self, 'Logout', 'Are you sure?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.config_data['login'] = {}
            self.restart_application()

    def closeEvent(self, event):
        login_prefs = self.config_data.get('login', {})
        if not login_prefs.get('stay_logged_in', False):
            login_prefs.pop('password', None)
            login_prefs.pop('username', None)
            login_prefs['remember_me'] = False
            self.config_data['login'] = login_prefs
        if QMessageBox.question(self, 'Exit', 'Are you sure?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.save_config()
            event.accept()
        else:
            event.ignore()

    def init_db(self):
        if not self.db_path: return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, projectName TEXT NOT NULL)')
                cursor.execute("PRAGMA table_info(projects)")
                existing_columns = [row[1] for row in cursor.fetchall()]
                all_columns_schema = {
                    "projectName": "TEXT NOT NULL", "projectLead": "TEXT", "status": "TEXT", 
                    "isTenderProject": "INTEGER", 
                    "isLimitedTenderProject": "INTEGER",      # <-- ADD THIS LINE
                    "departmentDetails": "TEXT", "departmentEnquiryDetails": "TEXT", "oemVendorDetails": "TEXT", 
                    "scopeOfWorkDetails": "TEXT", "proposalOrderDetails": "TEXT", "billOfMaterials": "TEXT", 
                    "oenDetails": "TEXT", "tenderDetails": "TEXT", 
                    "limitedTenderDetails": "TEXT",          # <-- AND ADD THIS LINE
                    "financialDetails": "TEXT", "fulfillmentDocs": "TEXT", 
                    "vendorPayments": "TEXT", "projectFolderPath": "TEXT", "createdAt": "TEXT", "updatedAt": "TEXT", 
                    "departmentId": "INTEGER"
                }
                for col_name, col_type in all_columns_schema.items():
                    if col_name not in existing_columns:
                        try:
                            cursor.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
                        except sqlite3.OperationalError as e:
                            if "duplicate column name" not in str(e): raise e
                conn.commit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Could not initialize or upgrade the database: {e}")
            self.close()
        utils.init_departments_db(self.departments_db_path)

    def update_project_status(self, project_data):
        bom_items = project_data.get('billOfMaterials', {}).get('items', [])
        if not bom_items:
            project_data['status'] = "PENDING"
            return
            
        items_with_qty = 0
        fulfilled_items = 0
        has_partial_fulfillment = False

        for item in bom_items:
            original_qty = float(item.get('qty', 0.0))
            if original_qty > 1e-9: # Consider this an item that needs fulfillment
                items_with_qty += 1
                total_fulfilled = sum(float(f.get('fulfilledQty', 0.0)) for f in item.get('fulfillments', []))
                
                if total_fulfilled >= original_qty - 1e-9:
                    fulfilled_items += 1
                elif total_fulfilled > 1e-9:
                    has_partial_fulfillment = True
        
        if items_with_qty == 0:
            project_data['status'] = "PENDING" # No items require fulfillment
        elif fulfilled_items == items_with_qty:
            project_data['status'] = "FULFILLED"
        elif fulfilled_items > 0 or has_partial_fulfillment:
            project_data['status'] = "PARTIALLY_FULFILLED"
        else:
            project_data['status'] = "PENDING"
            
    def create_project_specific_folder(self, project_data):
        """
        Creates a project-specific folder, now nested inside a department folder.
        The path will be .../Working_Folder/Department_Name/Project_Name/
        """
        if not self.working_folder: return None
        
        project_name = project_data.get('projectName', '')
        safe_project_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '_', '-')).rstrip().replace(" ", "_")
        if not safe_project_name:
            safe_project_name = f"project_{uuid.uuid4().hex[:8]}"

        # --- MODIFIED: Logic to create department sub-folder ---
        base_path = Path(self.working_folder)
        department_id = project_data.get('departmentId')
        
        # Get department name from the database
        if department_id:
            dept_info = utils.get_department_by_id(self.departments_db_path, department_id)
            if dept_info and dept_info.get('name'):
                safe_dept_name = "".join(c for c in dept_info['name'] if c.isalnum() or c in (' ', '_', '-')).rstrip().replace(" ", "_")
                base_path = base_path / safe_dept_name
        
        # The final project path is now nested
        project_path = base_path / safe_project_name
        # --- END MODIFICATION ---

        try:
            project_path.mkdir(parents=True, exist_ok=True)
            for sub_val in SUBFOLDER_NAMES.values():
                (project_path / sub_val).mkdir(parents=True, exist_ok=True)
            return str(project_path)
        except OSError as e:
            QMessageBox.critical(self, "Folder Creation Error", f"Could not create folder '{project_path}':\n{e}")
            return None

    def handle_save_and_go_home(self):
        current_frame = self.stacked_widget.currentWidget()
        if isinstance(current_frame, PageFrame) and not isinstance(current_frame, HomeView):
            if hasattr(current_frame, 'handle_save_and_return_home'):
                current_frame.handle_save_and_return_home()
        else:
            self.show_frame("HomeView")

    def handle_manual_backup(self):
        if not self.app_ready:
            QMessageBox.warning(self, "Not Ready", "Please select a working folder before backing up.")
            return
        if QMessageBox.information(self, "Manual Backup", "This will create a full backup of the current working folder.", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel) == QMessageBox.StandardButton.Ok:
            self.progress_dialog = QProgressDialog("Backing up data...", "Cancel", 0, 100, self)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.backup_thread = QThread()
            self.backup_worker = BackupWorker(self.working_folder, self.db_path, self.departments_db_path, is_manual=True)
            self.backup_worker.moveToThread(self.backup_thread)
            self.backup_thread.started.connect(self.backup_worker.run)
            self.backup_worker.finished.connect(lambda s: (self.progress_dialog.setValue(100), QMessageBox.information(self, "Success", "Manual backup completed successfully.") if s else None))
            self.backup_worker.error.connect(lambda e: (self.progress_dialog.close(), QMessageBox.critical(self, "Backup Error", e)))
            self.backup_worker.progress.connect(self.progress_dialog.setValue)
            self.backup_worker.finished.connect(self.backup_thread.quit)
            self.backup_worker.finished.connect(self.backup_worker.deleteLater)
            self.backup_thread.finished.connect(self.backup_thread.deleteLater)
            self.backup_thread.start()

    def restore_from_backup(self):
        if QMessageBox.warning(self, "Restore from Backup", "This will overwrite all current project data in this working folder.\n\nAre you absolutely sure you want to proceed?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
            
        backup_dir = utils.get_app_config_base_path() / "Global_Backups"
        backup_file, _ = QFileDialog.getOpenFileName(self, "Select Backup File", str(backup_dir), "ZIP Files (*.zip)")
        if not backup_file: return
            
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(backup_file, 'r') as zipf:
                    zipf.extractall(temp_dir)
                temp_path = Path(temp_dir)
                db_path_in_zip = next(temp_path.glob('*/workflow_app.db'), None)
                if not db_path_in_zip: raise FileNotFoundError("Backup is invalid: workflow_app.db not found.")
                
                working_folder_name_in_zip = db_path_in_zip.parent.name
                for item in Path(self.working_folder).iterdir():
                    if item.name != "backups":
                        if item.is_dir(): shutil.rmtree(item)
                        else: item.unlink()
                
                if (temp_path / 'departments.db').exists():
                    shutil.copy2(temp_path / 'departments.db', self.departments_db_path)
                
                source_wf = temp_path / working_folder_name_in_zip
                for item in source_wf.iterdir():
                    if item.is_dir(): shutil.copytree(item, Path(self.working_folder) / item.name)
                    else: shutil.copy2(item, self.working_folder)
            
            utils.log_activity(f"System restored from backup: {Path(backup_file).name}")
            QMessageBox.information(self, "Restore Complete", "Restore successful. The application will now restart.")
            self.restart_application()
        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", f"An error occurred during restore: {e}")

    def navigate_to_project_details(self, project_id):
        if project_id is not None:
            self.set_current_project_for_editing(project_id)
            self.show_frame("ProjectDetailsView")

    def save_project_to_sqlite(self, project_data, is_final_step=False):
        if not self.db_path: return False
        is_new_project = project_data.get('id') is None
        if not project_data.get('projectName', '').strip() and is_new_project: return False
        
        project_data['updatedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if is_new_project:
            project_data['createdAt'] = project_data['updatedAt']
            if self.working_folder and not project_data.get('projectFolderPath'):
                # --- MODIFIED: Pass the whole project_data dict ---
                project_data['projectFolderPath'] = self.create_project_specific_folder(project_data)
        
        data_for_sql = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in project_data.items() if k != 'id'}
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if not is_new_project:
                    update_fields = ", ".join([f"{key} = ?" for key in data_for_sql])
                    values = list(data_for_sql.values()) + [project_data['id']]
                    cursor.execute(f"UPDATE projects SET {update_fields} WHERE id = ?", tuple(values))
                else:
                    columns = ", ".join(data_for_sql.keys())
                    placeholders = ", ".join(["?"] * len(data_for_sql))
                    cursor.execute(f"INSERT INTO projects ({columns}) VALUES ({placeholders})", tuple(data_for_sql.values()))
                    project_data['id'] = cursor.lastrowid
                conn.commit()

            log_msg = f"New project '{project_data['projectName']}' created." if is_new_project else f"Project '{project_data['projectName']}' updated."
            utils.log_activity(log_msg, project_id=project_data['id'])
            
            self.current_project_data = project_data
            self.load_projects_from_sqlite() 
            if is_final_step: self.set_current_project_for_editing(None) 
            return True
        except (sqlite3.Error, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Save Error", f"An error occurred while saving: {e}")
            return False
            
    def populate_themes_menu(self):
        self.themes_menu.clear()
        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        no_theme_action = QAction("No Theme", self, checkable=True)
        no_theme_action.setData(None)
        no_theme_action.triggered.connect(lambda: self.apply_theme(None))
        self.themes_menu.addAction(no_theme_action)
        self.theme_action_group.addAction(no_theme_action)
        self.themes_menu.addSeparator()
        qss_files = sorted([f for f in os.listdir(self.themes_path) if f.endswith(('.qss', '.txt'))])
        for qss_file in qss_files:
            theme_name = Path(qss_file).stem.replace("_", " ").title()
            action = QAction(theme_name, self, checkable=True)
            action.setData(qss_file)
            action.triggered.connect(lambda checked, f=qss_file: self.apply_theme(f))
            self.themes_menu.addAction(action)
            self.theme_action_group.addAction(action)

    def _replace_qss_path(self, match):
        url_content = match.group(1).strip().strip("'\"")
        full_image_path = (self.themes_path / url_content).resolve()
        return f'url("{full_image_path.as_posix()}")'

    def _update_home_icon_based_on_theme(self):
        if not hasattr(self, 'home_menubar_button'): return
        theme_file = self.config_data.get('color_theme')
        theme_stem = Path(theme_file).stem if theme_file else ""
        icon_file = "home_icon_light.png" if theme_stem in DARK_THEMES else "home_icon_dark.png"
        icon_path = self.themes_path / icon_file
        if icon_path.exists():
            self.home_menubar_button.setIcon(QIcon(str(icon_path)))
            self.home_menubar_button.setIconSize(self.home_menubar_button.size() * 0.9)

    def apply_theme(self, qss_file_name):
        stylesheet = ""
        if qss_file_name:
            theme_path = self.themes_path / qss_file_name
            if theme_path.exists():
                try:
                    with open(theme_path, "r", encoding="utf-8") as f:
                        stylesheet = f.read()
                    stylesheet = re.sub(r'url\((.*?)\)', self._replace_qss_path, stylesheet)
                except Exception as e:
                    QMessageBox.critical(self, "Theme Error", f"Failed to apply theme: {e}")
        
        QApplication.instance().setStyleSheet(stylesheet)
        self.config_data['color_theme'] = qss_file_name
        if hasattr(self, 'theme_action_group'):
            for action in self.theme_action_group.actions():
                if (action.data() or None) == qss_file_name:
                    action.setChecked(True)
                    break
        self._update_home_icon_based_on_theme()

        base_stylesheet = """
            #TitleBarButton, #CloseButton { background-color: transparent; border: none; font-size: 14px; }
            QToolButton#UserIconMenuBarButton::menu-indicator { image: none; } /* <-- ADD THIS LINE */            
            #FormTitle { font-size: 24px; font-weight: bold; padding-bottom: 10px; }
            QLineEdit { border-radius: 5px; padding: 12px; font-size: 14px; border: 1px solid; }
            QCheckBox::indicator { width: 15px; height: 15px; border-radius: 3px; border: 1px solid; }
            #ActionButton { font-weight: bold; border-radius: 5px; padding: 12px; font-size: 14px; border: none; }
            #LinkButton { background-color: transparent; border: none; text-decoration: underline; }
        """
        self.setStyleSheet(stylesheet + base_stylesheet)        

    def show_frame(self, page_name):
        if not self.app_ready and page_name != "HomeView":
            QMessageBox.critical(self, "Setup Error", "Application is not ready.")
            return
            
        if page_name not in self.frames:
            page_class = self.page_classes.get(page_name)
            if not page_class:
                print(f"Error: Page class '{page_name}' not found.")
                return
            
            frame = page_class(controller=self)
            
            if hasattr(frame, 'navigate_request'):
                frame.navigate_request.connect(self.show_frame)
            if hasattr(frame, 'save_and_home_request'):
                frame.save_and_home_request.connect(lambda: self.show_frame("HomeView"))
            if hasattr(frame, 'quit_request'):
                frame.quit_request.connect(self.close)

            self.frames[page_name] = frame
            self.stacked_widget.addWidget(frame)
        
        current_frame = self.frames[page_name]
        self.stacked_widget.setCurrentWidget(current_frame)
        if hasattr(current_frame, 'on_show'):
            current_frame.on_show()
            
    def complete_initial_setup(self):
        self.populate_themes_menu()
        self.apply_theme(self.config_data.get("color_theme"))
        
        # This is the 'if' statement from line 707
        if not self.working_folder or not Path(self.working_folder).is_dir():
            # This block MUST be indented
            default_path = Path.home() / "Documents" / "WORKFLOW_Projects"
            default_path.mkdir(parents=True, exist_ok=True)
            self.set_working_folder(str(default_path))
            QMessageBox.information(self, "Welcome!", f"Default folder created at:\n{default_path}")
        
        # This block MUST be "dedented" to the same level as the 'if' statement
        self.db_path = Path(self.working_folder) / 'workflow_app.db'
        self.init_db()
        utils.log_activity("Application started.")
        self.app_ready = True
        self.show_frame("HomeView")
        self.statusBar().showMessage(f"Ready. Logged in as: {self.current_user_data.get('username', 'Guest')}", 3000)
        
        self._apply_shadow_to_menus()
        
        self._update_home_icon_based_on_theme()
        self._update_user_profile_ui()

    def load_config(self):
        config_path = utils.get_app_config_path()
        defaults = {"working_folder": "", "color_theme": None, "login": {}}
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f: self.config_data = json.load(f)
            else: self.config_data = defaults
        except (json.JSONDecodeError, IOError):
            self.config_data = defaults
        
        self.working_folder = self.config_data.get("working_folder", "")

    def prompt_for_working_folder(self):
        folder_selected = QFileDialog.getExistingDirectory(self, "Select Working Folder")
        if folder_selected and folder_selected != self.working_folder:
            self.set_working_folder(folder_selected)
            QMessageBox.information(self, "Folder Changed", "Application will now restart.")
            self.restart_application()

    def set_working_folder(self, folder_path):
        self.working_folder = folder_path
        self.config_data['working_folder'] = folder_path
        self.save_config()

    def save_config(self):
        try:
            with open(utils.get_app_config_path(), 'w') as f: json.dump(self.config_data, f, indent=4)
        except Exception as e: print(f"Error saving config: {e}")

    def restart_application(self):
        self.save_config()
        os.execl(sys.executable, sys.executable, *sys.argv)
    
    def select_working_folder_menu_action(self):
        self.prompt_for_working_folder()
        
    def setup_icon(self):
        icon_path = BASE_PATH / DEFAULT_ICON_PATH
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def show_admin_login(self):
        if not self.app_ready: return
        self.show_frame("AdminDepartmentView")
        
    def show_about_dialog(self): 
        # The old line is commented out and replaced
        # QMessageBox.about(self, f"About WORKFLOW v{APP_VERSION}", f"WORKFLOW Project Management\nVersion: {APP_VERSION}")
        dialog = AboutDialog(self)
        dialog.exec()


    def load_projects_from_sqlite(self):
        if not self.db_path or not Path(self.db_path).exists():
            self.all_projects_data = []
            if self.app_ready:
                home_view = self.frames.get("HomeView")
                if home_view: home_view.refresh_project_list()
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM projects ORDER BY updatedAt DESC, id DESC")
                self.all_projects_data = []
                for row in cursor.fetchall():
                    project = dict(row)
                    for key, template_val in initial_project_data_template.items():
                        if isinstance(template_val, (dict, list)):
                            if project.get(key) and isinstance(project[key], str):
                                try: project[key] = json.loads(project[key])
                                except json.JSONDecodeError: project[key] = copy.deepcopy(template_val)
                            elif project.get(key) is None: project[key] = copy.deepcopy(template_val)
                    self.all_projects_data.append(project)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error loading projects: {e}")
            self.all_projects_data = []
        if self.app_ready:
            home_view = self.frames.get("HomeView")
            if home_view: home_view.refresh_project_list()
        
    def set_current_project_for_editing(self, project_id=None):
        if project_id is not None:
            project_from_list = next((p for p in self.all_projects_data if p.get('id') == project_id), None)
            if project_from_list:
                self.current_project_data = copy.deepcopy(project_from_list)
            else:
                self.current_project_data = copy.deepcopy(initial_project_data_template)
        else:
            self.current_project_data = copy.deepcopy(initial_project_data_template)

    def get_project_bom_total(self):
        if not self.current_project_data: return 0.0
        bom_data = self.current_project_data.get('billOfMaterials', {})
        if not bom_data: return 0.0
        bom_items = bom_data.get('items', [])
        total_sum = sum(float(item.get('total', 0.0)) for item in bom_items)
        return total_sum
            
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    main_win = WorkflowApp() 
    
    user_data = None
    login_prefs = main_win.config_data.get('login', {})
    
    remembered_username = login_prefs.get('username')
    # CORRECTED: Get the specific state for each checkbox
    remember_me_state = login_prefs.get('remember_me', False)
    stay_logged_in_state = login_prefs.get('stay_logged_in', False)
    
    should_load_pass = stay_logged_in_state or remember_me_state
    remembered_password = login_prefs.get('password') if should_load_pass else None

    login_dialog = LoginSignUpDialog(
        app_version=APP_VERSION, # <-- ADD THIS ARGUMENT        
        initial_username=remembered_username,
        initial_password=remembered_password,
        # PASS THE STATES to the dialog
        remember_me=remember_me_state,
        stay_logged_in=stay_logged_in_state
    )
    
    user_container = [None]
    login_dialog.loggedIn.connect(lambda data: user_container.__setitem__(0, data))

    if login_dialog.exec() == QDialog.DialogCode.Accepted:
        user_data = user_container[0]
        if user_data:
            should_remember_creds = login_dialog.remember_me_checkbox.isChecked()
            should_stay_in = login_dialog.stay_logged_in_checkbox.isChecked()

            if should_remember_creds or should_stay_in:
                login_prefs['username'] = user_data['username']
                login_prefs['remember_me'] = True
                login_prefs['password'] = login_dialog.signin_password_entry.text()
            else:
                login_prefs.pop('username', None)
                login_prefs.pop('password', None)
                login_prefs['remember_me'] = False
            
            login_prefs['stay_logged_in'] = should_stay_in
            main_win.config_data['login'] = login_prefs
            main_win.save_config()
        else:
            sys.exit(1)
    else:
        sys.exit(0)

    if user_data:
        main_win.current_user_data = user_data
        main_win.complete_initial_setup()
        main_win.show()
        sys.exit(app.exec())
