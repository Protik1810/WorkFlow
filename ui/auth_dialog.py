# ui/auth_dialog.py
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

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,QCheckBox,QFrame,
    QPushButton, QMessageBox, QStackedWidget, QWidget, QFileDialog, QToolButton
)
from PyQt6.QtGui import QPixmap, QColor, QPalette, QBrush, QFont, QCursor
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer, QDateTime
import darkdetect

import utils
import config
from pathlib import Path

class LoginSignUpDialog(QDialog):
    loggedIn = pyqtSignal(dict)
    minimize_app_request = pyqtSignal()

    def __init__(self, parent=None, app_version="N/A", initial_username=None, initial_password=None, remember_me=False, stay_logged_in=False):
        super().__init__(parent)
        self.setWindowTitle("WORKFLOW - Authentication")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(900, 600)
        self.setModal(True) 
        
        self.app_version = app_version
        self.user_db_path = utils.get_users_database_path()
        utils.init_users_db(self.user_db_path)
        self._old_pos = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = self._create_title_bar()
        main_layout.addWidget(self.title_bar)
        
        content_layout = QHBoxLayout(); content_layout.setSpacing(0)
        self.left_pane = self._create_left_pane(initial_username, initial_password, remember_me, stay_logged_in)
        content_layout.addWidget(self.left_pane)
        self.right_pane = self._create_right_pane()
        content_layout.addWidget(self.right_pane, 1)
        main_layout.addLayout(content_layout)
        self._apply_global_styles()

    def _create_title_bar(self):
        title_bar = QWidget(self, objectName="TitleBar")
        title_bar.setFixedHeight(32)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 0, 0)
        
        title_label = QLabel(self.windowTitle())
        layout.addWidget(title_label)
        layout.addStretch()

        self.min_button = QPushButton("__")
        self.min_button.clicked.connect(self.showMinimized)
        self.min_button.setObjectName("TitleBarButton")
        self.min_button.setFixedSize(45, 32)

        self.close_button = QPushButton("✕")
        self.close_button.clicked.connect(self.reject)
        self.close_button.setObjectName("CloseButton")
        self.close_button.setFixedSize(45, 32)

        layout.addWidget(self.min_button)
        layout.addWidget(self.close_button)
        
        return title_bar

    def _create_left_pane(self, username, password, remember_me, stay_logged_in):
        left_pane = QWidget(objectName="LeftPane")
        left_pane.setFixedWidth(350)
        
        layout = QVBoxLayout(left_pane)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.addWidget(self._create_signin_page(username, password, remember_me, stay_logged_in))
        self.stacked_widget.addWidget(self._create_signup_page())
        layout.addWidget(self.stacked_widget)
        
        layout.addStretch() # <-- MOVED: This spacer now pushes everything below it to the bottom

        # Version Label
        version_label = QLabel(f"Version {self.app_version}")
        version_label.setObjectName("VersionLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(version_label) # The label is now correctly placed before the buttons


        self.toggle_signup_button = QPushButton("Don't have an account? Sign Up", objectName="LinkButton")
        self.toggle_signup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_signup_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        self.toggle_signin_button = QPushButton("Already have an account? Sign In", objectName="LinkButton")
        self.toggle_signin_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_signin_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        
        layout.addWidget(self.toggle_signup_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.toggle_signin_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.toggle_signin_button.hide()
        self.stacked_widget.currentChanged.connect(lambda i: (self.toggle_signup_button.setVisible(i==0), self.toggle_signin_button.setVisible(i==1)))

        return left_pane

    def _create_right_pane(self):
        right_pane = QWidget(objectName="RightPane")
        layout = QVBoxLayout(right_pane)
        layout.setContentsMargins(40, 40, 40, 40)

        # Prominent Logo
        logo_label = QLabel()
        logo_path_str = utils.resource_path(config.DEFAULT_LOGO_PATH)
        if Path(logo_path_str).exists():
            pixmap = QPixmap(logo_path_str).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        
        # App Title and Tagline
        title_label = QLabel("WORKFLOW", objectName="AppNameLabel")
        tagline_label = QLabel("Project Management, Perfected.", objectName="TaglineLabel")

        # --- NEW: Create labels for both time and date ---
        self.time_label = QLabel(objectName="TimeLabel")
        self.date_label = QLabel(objectName="DateLabel")

        # --- MODIFIED: Timer now updates every second for the clock ---
        timer = QTimer(self)
        timer.timeout.connect(self._update_time_and_date) # Connect to the new method
        timer.start(1000) # Update every 1000 ms (1 second)
        self._update_time_and_date() # Initial call

        # Layout Arrangement
        layout.addStretch(1)
        layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(2)
        layout.addWidget(self.time_label, 0, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self.date_label, 0, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom)
        
        return right_pane

    def _update_time_and_date(self):
        """Updates both the time and date display."""
        current_datetime = QDateTime.currentDateTime()
        time_str = current_datetime.toString("hh:mm:ss AP")
        date_str = current_datetime.toString("dddd, MMMM d, yyyy")
        self.time_label.setText(time_str)
        self.date_label.setText(date_str)


    def _create_password_field(self, placeholder_text):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        password_edit = QLineEdit(placeholderText=placeholder_text)
        password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        toggle_button = QToolButton(text="Show", objectName="LinkButton")
        toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)

        def toggle_visibility():
            if password_edit.echoMode() == QLineEdit.EchoMode.Password:
                password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
                toggle_button.setText("Hide")
            else:
                password_edit.setEchoMode(QLineEdit.EchoMode.Password)
                toggle_button.setText("Show")
        
        toggle_button.clicked.connect(toggle_visibility)
        
        layout.addWidget(password_edit)
        layout.addWidget(toggle_button)

        return container, password_edit

    def _create_signin_page(self, username, password, remember_me, stay_logged_in):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        
        title = QLabel("Sign In", objectName="FormTitle")
        layout.addWidget(title)

        self.signin_username_entry = QLineEdit(placeholderText="Username")
        password_widget, self.signin_password_entry = self._create_password_field("Password")

        if username: self.signin_username_entry.setText(username)
        if password: self.signin_password_entry.setText(password)
        
        layout.addWidget(self.signin_username_entry)
        layout.addWidget(password_widget)

        self.remember_me_checkbox = QCheckBox("Remember Me")
        self.stay_logged_in_checkbox = QCheckBox("Stay Signed In")
        self.remember_me_checkbox.setChecked(remember_me)
        self.stay_logged_in_checkbox.setChecked(stay_logged_in)
            
        layout.addWidget(self.remember_me_checkbox)
        layout.addWidget(self.stay_logged_in_checkbox)
        
        layout.addWidget(QPushButton("Sign In", clicked=self._handle_signin, objectName="ActionButton"))

        return page
        
    def _create_signup_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)

        title = QLabel("Create Account", objectName="FormTitle")
        layout.addWidget(title)

        self.signup_username_entry = QLineEdit(placeholderText="Username")
        self.signup_full_name_entry = QLineEdit(placeholderText="Full Name")
        self.signup_email_entry = QLineEdit(placeholderText="Email (Optional)")
        password_widget, self.signup_password_entry = self._create_password_field("Password")
        confirm_widget, self.signup_confirm_password_entry = self._create_password_field("Confirm Password")
        
        layout.addWidget(self.signup_username_entry)
        layout.addWidget(self.signup_full_name_entry)
        layout.addWidget(self.signup_email_entry)
        layout.addWidget(password_widget)
        layout.addWidget(confirm_widget)
        
        layout.addWidget(QPushButton("Sign Up", clicked=self._handle_signup, objectName="ActionButton"))

        return page

    def _apply_global_styles(self):
        theme = darkdetect.theme()
        
        if theme == "Dark":
            stylesheet = """
                #AppNameLabel { color: #ffffff; font-size: 36px; font-weight: bold; }
                #TaglineLabel { color: #a0a0a0; font-size: 14px; }
                #TimeLabel { color: #ffffff; font-size: 28px; font-weight: bold; }
                #DateLabel { color: #505561; font-size: 12px; }
                #VersionLabel { color: #505561; font-size: 10px; }
                #LeftPane { background-color: #252830; }
                #RightPane, LoginSignUpDialog { background-color: #1e1e26; }
                #TitleBar { background-color: #252830; color: #a0a0a0; }
                #TitleBarButton { color: #a0a0a0; } #TitleBarButton:hover { background-color: #3d414d; }
                #CloseButton:hover { background-color: #e81123; color: #ffffff; }
                #FormTitle { color: #ffffff; }
                QLineEdit { background-color: #1e1e26; color: #e0e0e0; border-color: #3d414d; padding-right: 50px; }
                QLineEdit:focus { border-color: #0078d4; }
                QCheckBox { color: #a0a0a0; }
                QCheckBox::indicator { border-color: #3d414d; }
                QCheckBox::indicator:checked { background-color: #0078d4; border-color: #0078d4; }
                #ActionButton { background-color: #0078d4; color: #ffffff; }
                #ActionButton:hover { background-color: #005a9e; }
                #LinkButton { color: #0078d4; border: none; background-color: transparent; } #LinkButton:hover { color: #289fef; }
            """
        else:
            stylesheet = """
                #AppNameLabel { color: #000000; font-size: 36px; font-weight: bold; }
                #TaglineLabel { color: #505050; font-size: 14px; }
                #TimeLabel { color: #000000; font-size: 28px; font-weight: bold; }
                #DateLabel { color: #b0b0b0; font-size: 12px; }
                #VersionLabel { color: #b0b0b0; font-size: 10px; }
                #LeftPane { background-color: #ffffff; }
                #RightPane, LoginSignUpDialog { background-color: #f0f0f0; }
                #TitleBar { background-color: #ffffff; color: #505050; border-bottom: 1px solid #dcdcdc; }
                #TitleBarButton { color: #505050; } #TitleBarButton:hover { background-color: #e6e6e6; }
                #CloseButton:hover { background-color: #e81123; color: #ffffff; }
                #FormTitle { color: #000000; }
                QLineEdit { background-color: #f0f0f0; color: #000000; border-color: #dcdcdc; padding-right: 50px; }
                QLineEdit:focus { border-color: #0078d4; }
                QCheckBox { color: #505050; }
                QCheckBox::indicator { border-color: #dcdcdc; }
                QCheckBox::indicator:checked { background-color: #0078d4; border-color: #0078d4; }
                #ActionButton { background-color: #0078d4; color: #ffffff; }
                #ActionButton:hover { background-color: #005a9e; }
                #LinkButton { color: #0078d4; border: none; background-color: transparent; } #LinkButton:hover { color: #005a9e; }
            """

        base_stylesheet = """
            #TitleBarButton, #CloseButton { background-color: transparent; border: none; font-size: 14px; }
            #FormTitle { font-size: 24px; font-weight: bold; padding-bottom: 10px; }
            QLineEdit { border-radius: 5px; padding: 12px; font-size: 14px; border: 1px solid; }
            QCheckBox::indicator { width: 15px; height: 15px; border-radius: 3px; border: 1px solid; }
            #ActionButton { font-weight: bold; border-radius: 5px; padding: 12px; font-size: 14px; border: none; }
        """
        self.setStyleSheet(stylesheet + base_stylesheet)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.underMouse(): self._old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if self._old_pos: self.move(self.pos() + (event.globalPosition().toPoint() - self._old_pos)); self._old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event): self._old_pos = None

    def _handle_signin(self):
        username = self.signin_username_entry.text().strip()
        password = self.signin_password_entry.text()
        if not username or not password:
            QMessageBox.warning(self, "Input Error", "Please enter username and password.")
            return

        user_data = utils.get_user_by_username(self.user_db_path, username)
        if user_data and utils.check_password(user_data['password_hash'], password):
            self.loggedIn.emit(user_data)
            self.accept()
        else:
            QMessageBox.critical(self, "Login Failed", "Invalid username or password.")
            
    def _handle_signup(self):
        username = self.signup_username_entry.text().strip()
        full_name = self.signup_full_name_entry.text().strip()
        password = self.signup_password_entry.text()
        confirm_password = self.signup_confirm_password_entry.text()
        
        if not all([username, full_name, password]):
            QMessageBox.warning(self, "Input Error", "Username, Full Name, and Password are required.")
            return
        if password != confirm_password:
            QMessageBox.warning(self, "Password Mismatch", "Passwords do not match.")
            return

        user_id = utils.add_user(self.user_db_path, username, password, full_name=full_name, email=self.signup_email_entry.text().strip())
        if user_id:
            QMessageBox.information(self, "Success", "Account created successfully!")
            self.stacked_widget.setCurrentIndex(0)
        else:
            QMessageBox.warning(self, "Sign Up Failed", "Username already exists.")