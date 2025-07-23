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

import sys
import os
import subprocess
import datetime
import textwrap
import shutil
import uuid
import json
from pathlib import Path

import fitz  # PyMuPDF
from PyQt6.QtGui import QImage, QPixmap

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,QTableWidgetItem,QTableWidget,
    QLineEdit, QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox,QStackedWidget,
    QSizePolicy, QFrame, QScrollArea, QTabWidget, QTextEdit, QComboBox,QCheckBox,QSplitter,
    QDialog, QDialogButtonBox, QDateEdit, QFileDialog, QTextBrowser, QStyledItemDelegate, QStyleOptionViewItem
)

# Add QDesktopServices and QUrl for clickable links
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QSize,QModelIndex,QTimer, QDate
from PyQt6.QtGui import (
    QFont, QColor, QBrush, QDesktopServices, QImage, QPixmap, QPainter,
    QTextDocument, QAbstractTextDocumentLayout, 
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter



from .base_frame import PageFrame
from config import SUBFOLDER_NAMES
import utils

# ========================================================================
# NEW: Text Edit Delegate to allow multi-line text editing in table cells
# ========================================================================

class TextEditDelegate(QStyledItemDelegate):
    """A custom delegate to allow multi-line text editing in table cells."""
    def createEditor(self, parent, option, index):
        editor = QTextEdit(parent)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        editor.setText(str(value))

    def setModelData(self, editor, model, index):
        value = editor.toPlainText()
        model.setData(index, value, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

# =======================================================================
# New Class
# =========================================================================
class EditFulfillmentEventDialog(QDialog):
    """A dialog to edit the details of a fulfillment event (e.g., an invoice or challan)."""
    def __init__(self, event_data, project_folder_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Fulfillment Event")
        self.setMinimumWidth(500)
        self.event_data = event_data
        self.project_folder_path = Path(project_folder_path) if project_folder_path else None
        self.docs_to_delete_on_ok = [] # Store paths of files to be deleted

        layout = QVBoxLayout(self)

        # Form for Ref No and Date
        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Reference No:"), 0, 0)
        self.ref_entry = QLineEdit(self.event_data.get('refNo', ''))
        form_layout.addWidget(self.ref_entry, 0, 1)

        form_layout.addWidget(QLabel("Date:"), 1, 0)
        self.date_edit = QDateEdit(calendarPopup=True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        current_date_str = self.event_data.get('date', '')
        if current_date_str:
            self.date_edit.setDate(datetime.datetime.strptime(current_date_str, "%Y-%m-%d").date())
        layout.addLayout(form_layout)

        # Document Management
        layout.addWidget(QLabel("<b>Associated Documents:</b>"))
        doc_button_layout = QHBoxLayout()
        add_doc_button = QPushButton("Add File(s)"); add_doc_button.clicked.connect(self._add_files)
        remove_doc_button = QPushButton("Remove Selected"); remove_doc_button.clicked.connect(self._remove_file)
        doc_button_layout.addStretch()
        doc_button_layout.addWidget(add_doc_button)
        doc_button_layout.addWidget(remove_doc_button)
        layout.addLayout(doc_button_layout)
        
        self.doc_tree = QTreeWidget()
        self.doc_tree.setHeaderHidden(True)
        layout.addWidget(self.doc_tree)
        self._refresh_doc_tree()

        # Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _refresh_doc_tree(self):
        self.doc_tree.clear()
        for doc in self.event_data.get('documents', []):
            item = QTreeWidgetItem([doc.get('name', 'Unnamed File')])
            item.setData(0, Qt.ItemDataRole.UserRole, doc)
            self.doc_tree.addTopLevelItem(item)
    
    def _add_files(self):
        if not self.project_folder_path:
            QMessageBox.critical(self, "Error", "Project folder path is not set. Cannot add files.")
            return

        filepaths, _ = QFileDialog.getOpenFileNames(self, "Select Document(s)")
        if not filepaths:
            return

        target_subfolder = SUBFOLDER_NAMES.get("fulfillmentDocuments", "Fulfillment_Documents")
        target_path = self.project_folder_path / target_subfolder
        target_path.mkdir(parents=True, exist_ok=True)
        
        for fp_str in filepaths:
            original_file = Path(fp_str)
            destination_path = target_path / original_file.name
            try:
                shutil.copy2(original_file, destination_path)
                new_doc = {
                    'name': original_file.name,
                    'path': str(destination_path.relative_to(self.project_folder_path)),
                    'type': 'project_file'
                }
                self.event_data['documents'].append(new_doc)
            except Exception as e:
                QMessageBox.critical(self, "File Copy Error", f"Could not copy file: {e}")
        self._refresh_doc_tree()

    def _remove_file(self):
        selected = self.doc_tree.currentItem()
        if not selected:
            return
        
        doc_to_remove = selected.data(0, Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(self, "Confirm Removal", 
            f"Are you sure you want to remove the reference to '{doc_to_remove['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.event_data['documents'].remove(doc_to_remove)
            # Ask to delete the physical file
            if self.project_folder_path and doc_to_remove.get('path'):
                reply_delete = QMessageBox.question(self, "Delete File?",
                    "Do you also want to delete the actual file from the project folder?\nThis cannot be undone.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply_delete == QMessageBox.StandardButton.Yes:
                    self.docs_to_delete_on_ok.append(self.project_folder_path / doc_to_remove['path'])
            self._refresh_doc_tree()

    def get_updated_data(self):
        """Called after the dialog is accepted to get the final data."""
        self.event_data['refNo'] = self.ref_entry.text().strip()
        self.event_data['date'] = self.date_edit.date().toString("yyyy-MM-dd")
        # Delete marked files
        for f_path in self.docs_to_delete_on_ok:
            try:
                f_path.unlink(missing_ok=True)
            except Exception as e:
                print(f"Could not delete file {f_path}: {e}")
        return self.event_data


# ========================================================================
# NEW: Custom Text Browser to Reliably Handle External Links
# ========================================================================
class LinkInterceptingBrowser(QTextBrowser):
    """
    A QTextBrowser that intercepts clicks on links, opens them externally,
    and prevents the widget from trying to navigate internally.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)

    def mousePressEvent(self, event):
        # Check if the click is on a link (anchor)
        anchor = self.anchorAt(event.pos())
        if anchor:
            # If it is, open the link externally using the OS.
            QDesktopServices.openUrl(QUrl(anchor))
            # And then do nothing else. This prevents the widget from
            # trying to load the file and showing the error.
            return
        # If the click was not on a link, perform the default action.
        super().mousePressEvent(event)


# ========================================================================
# NEW: Custom Delegate for Word Wrapping Tree Widget Items
# ========================================================================
class WordWrapDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        if index.column() == 2:
            text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
            doc = QTextDocument()
            doc.setDefaultFont(option.font)
            doc.setPlainText(text)
            doc.setTextWidth(option.rect.width())
            painter.save()
            painter.translate(option.rect.topLeft())
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.palette = option.palette
            doc.documentLayout().draw(painter, ctx)
            painter.restore()
        else:
            super().paint(painter, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        if index.column() == 2:
            text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
            doc = QTextDocument()
            doc.setDefaultFont(option.font)
            doc.setPlainText(text)
            doc.setTextWidth(option.rect.width())
            return QSize(int(doc.idealWidth()), int(doc.size().height()))
        return super().sizeHint(option, index)

# ========================================================================
# Class: HomeView (Corrected Layout)
# ========================================================================

class HomeView(PageFrame):
    def __init__(self, controller):
        super().__init__(controller)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Top Search Area (Advanced Search only) ---
        advanced_search_frame = QFrame()
        advanced_search_frame.setObjectName("CardFrame")
        search_grid = QGridLayout(advanced_search_frame)
        self.search_name_entry = QLineEdit()
        self.search_lead_combo = QComboBox()
        self.search_dept_combo = QComboBox()
        self.search_status_combo = QComboBox()
        self.search_status_combo.addItems(["All", "PENDING", "PARTIALLY_FULFILLED", "FULFILLED"])
        search_grid.addWidget(QLabel("Project Name:"), 0, 0); search_grid.addWidget(self.search_name_entry, 0, 1)
        search_grid.addWidget(QLabel("Project Lead:"), 0, 2); search_grid.addWidget(self.search_lead_combo, 0, 3)
        search_grid.addWidget(QLabel("Department:"), 1, 0); search_grid.addWidget(self.search_dept_combo, 1, 1)
        search_grid.addWidget(QLabel("Status:"), 1, 2); search_grid.addWidget(self.search_status_combo, 1, 3)
        search_buttons_layout = QHBoxLayout()
        self.execute_search_button = QPushButton("Search"); self.execute_search_button.clicked.connect(self.execute_advanced_search)
        self.clear_search_button = QPushButton("Clear"); self.clear_search_button.clicked.connect(self.clear_advanced_search)
        search_buttons_layout.addStretch(1); search_buttons_layout.addWidget(self.clear_search_button); search_buttons_layout.addWidget(self.execute_search_button)
        search_grid.addLayout(search_buttons_layout, 2, 0, 1, 4)
        self.main_layout.addWidget(advanced_search_frame)

        # --- Main Content Area (with QSplitter) ---
        main_content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left Panel (Project List) ---
        left_panel = QWidget()
        left_panel_layout = QVBoxLayout(left_panel)
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabels(["SL. No.", "Projects", "Department", "Project Lead", "Status"])
        self.project_tree.itemDoubleClicked.connect(self.on_project_double_click)
        left_panel_layout.addWidget(self.project_tree)
        
        project_actions_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh List"); self.refresh_button.clicked.connect(self.controller.load_projects_from_sqlite)
        self.edit_update_button = QPushButton("EDIT/UPDATE PROJECT"); self.edit_update_button.clicked.connect(self.edit_selected_project)
        project_actions_layout.addStretch(1)
        project_actions_layout.addWidget(self.refresh_button)
        project_actions_layout.addWidget(self.edit_update_button)
        left_panel_layout.addLayout(project_actions_layout)
        
        # --- Right Panel (Activity Log & Actions) ---
        right_panel = QWidget()
        right_panel_layout = QVBoxLayout(right_panel)
        self.new_project_button = QPushButton("NEW PROJECT CREATION"); self.new_project_button.clicked.connect(self.create_new_project)
        self.open_folder_button = QPushButton("OPEN PROJECT FOLDER"); self.open_folder_button.clicked.connect(self.open_project_folder_action)
        self.preview_button = QPushButton("PROJECT PREVIEW"); self.preview_button.clicked.connect(self.preview_project_action)
        self.details_button = QPushButton("PROJECT DETAILS"); self.details_button.setObjectName("DetailsButton"); self.details_button.clicked.connect(self.view_project_details)
        self.exit_button_home = QPushButton("EXIT"); self.exit_button_home.setObjectName("ExitButton"); self.exit_button_home.clicked.connect(self.handle_exit)

        right_panel_layout.addWidget(self.new_project_button)
        right_panel_layout.addWidget(self.open_folder_button)
        right_panel_layout.addWidget(self.preview_button)
        right_panel_layout.addWidget(self.details_button)
        
        log_label = QLabel("Latest Updates:"); log_label.setStyleSheet("font-weight: bold; margin-top: 15px;")
        self.log_viewer = QTreeWidget()
        self.log_viewer.setHeaderLabels(["Date", "Time", "Activity"])
        self.log_viewer.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.log_viewer.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.log_viewer.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.log_viewer.itemClicked.connect(self.handle_log_item_click)
        self.log_viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        right_panel_layout.addWidget(log_label)
        right_panel_layout.addWidget(self.log_viewer, 1)
        right_panel_layout.addWidget(self.exit_button_home)

        # Add panels to the splitter
        main_content_splitter.addWidget(left_panel)
        main_content_splitter.addWidget(right_panel)
        main_content_splitter.setSizes([600, 400])

        self.main_layout.addWidget(main_content_splitter, 1)
        
        # --- Bottom Bar ---
        bottom_bar_layout = QHBoxLayout()
        self.select_folder_button = QPushButton("Change Working Folder")
        self.select_folder_button.clicked.connect(self.controller.select_working_folder_menu_action)
        self.working_folder_display_text_label = QLabel("Working Folder: <NOT SET>")
        self.working_folder_display_text_label.setObjectName("WorkingFolderLabel")
        self.working_folder_display_text_label.setWordWrap(True)
        bottom_bar_layout.addWidget(self.select_folder_button)
        bottom_bar_layout.addWidget(self.working_folder_display_text_label, 1)
        self.main_layout.addLayout(bottom_bar_layout)
        
        self.toggle_ui_elements(self.controller.app_ready)

    def on_show(self):
        super().on_show()
        self.update_working_folder_display()
        self.toggle_ui_elements(self.controller.app_ready)
        if self.controller.app_ready:
            self.controller.load_projects_from_sqlite()
            self.refresh_project_list()
            self.populate_dept_search()
            self.populate_lead_search()
            self.load_activity_log()

    def populate_dept_search(self):
        current_selection = self.search_dept_combo.currentText()
        self.search_dept_combo.clear()
        self.search_dept_combo.addItem("All")
        departments = utils.get_all_departments_from_db(self.controller.departments_db_path)
        self.search_dept_combo.addItems([d['name'] for d in departments])
        self.search_dept_combo.setCurrentText(current_selection)

    def populate_lead_search(self):
        current_selection = self.search_lead_combo.currentText()
        self.search_lead_combo.clear()
        self.search_lead_combo.addItem("All")
        
        if self.controller.all_projects_data:
            leads = sorted(list(set(p.get('projectLead', '') for p in self.controller.all_projects_data if p.get('projectLead'))))
            self.search_lead_combo.addItems(leads)
        
        self.search_lead_combo.setCurrentText(current_selection)

    def execute_advanced_search(self):
        if not self.controller.app_ready: return
        name_q = self.search_name_entry.text().strip().lower()
        lead_q = self.search_lead_combo.currentText()
        dept_q = self.search_dept_combo.currentText()
        status_q = self.search_status_combo.currentText()
        
        filtered_projects = self.controller.all_projects_data
        if name_q: filtered_projects = [p for p in filtered_projects if name_q in p.get('projectName', '').lower()]
        
        if lead_q != "All":
            filtered_projects = [p for p in filtered_projects if p.get('projectLead', '') == lead_q]
            
        if dept_q != "All":
            dept_id = next((d['id'] for d in utils.get_all_departments_from_db(self.controller.departments_db_path) if d['name'] == dept_q), None)
            if dept_id is not None:
                filtered_projects = [p for p in filtered_projects if p.get('departmentId') == dept_id]
        if status_q != "All":
            filtered_projects = [p for p in filtered_projects if p.get('status', '') == status_q]
        
        self.refresh_project_list(projects_to_display=filtered_projects)

    def clear_advanced_search(self):
        self.search_name_entry.clear()
        self.search_lead_combo.setCurrentIndex(0)
        self.search_dept_combo.setCurrentIndex(0)
        self.search_status_combo.setCurrentIndex(0)
        self.refresh_project_list()
        
    def refresh_project_list(self, projects_to_display=None):
        self.project_tree.clear()
        if not self.controller.app_ready: 
            self.toggle_ui_elements(False)
            return
        
        projects = projects_to_display if projects_to_display is not None else self.controller.all_projects_data
        
        if not projects: 
            self.project_tree.addTopLevelItem(QTreeWidgetItem(["", "No projects found."]))
            return
        
        for i, p in enumerate(projects):
            dept_info = utils.get_department_by_id(self.controller.departments_db_path, p.get('departmentId'))
            department_name = dept_info['name'] if dept_info else "N/A"
            
            # --- THIS IS THE CHANGE ---
            # Call the new controller method to get a detailed status
            status = self.controller.get_detailed_status(p)
            
            item = QTreeWidgetItem([
                str(i + 1), 
                p.get('projectName', 'N/A'), 
                department_name, 
                p.get('projectLead', 'N/A'), 
                status  # Use the new detailed status string
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, p.get('id'))
            
            # Color logic for base status
            base_status = p.get('status', 'PENDING')
            status_column_index = 4
            if base_status == "FULFILLED":
                item.setForeground(status_column_index, QBrush(QColor("darkgreen")))
            elif base_status == "PARTIALLY_FULFILLED":
                item.setForeground(status_column_index, QBrush(QColor("darkorange")))
            
            self.project_tree.addTopLevelItem(item)
            
    def handle_log_item_click(self, item, column):
        project_id = item.data(0, Qt.ItemDataRole.UserRole)
        if project_id: self.controller.navigate_to_project_details(project_id)

    def load_activity_log(self):
        self.log_viewer.clear()
        log_file = utils.get_app_config_base_path() / "activity_log.json"
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f: lines = f.readlines()[-200:]
                log_items = [json.loads(line) for line in lines if line.strip()]
                for log_data in reversed(log_items):
                    # Parse the UTC timestamp from the log file
                    dt_obj_utc = datetime.datetime.fromisoformat(log_data["timestamp"]) #
                    
                    # Convert UTC time to the user's local timezone
                    dt_obj_local = dt_obj_utc.astimezone(None)
                    
                    # Use the local time object for display
                    item = QTreeWidgetItem([dt_obj_local.strftime("%d-%m-%Y"), dt_obj_local.strftime("%I:%M:%S:%p"), log_data.get("message", "")])

                    if log_data.get("project_id"):
                        item.setData(0, Qt.ItemDataRole.UserRole, log_data["project_id"])
                        item.setForeground(2, QBrush(QColor("#0969DA")))
                    self.log_viewer.addTopLevelItem(item)
                self.log_viewer.resizeColumnToContents(0); self.log_viewer.resizeColumnToContents(1)
            except Exception as e:
                self.log_viewer.addTopLevelItem(QTreeWidgetItem([f"Error reading log file: {e}"]))
        else:
            self.log_viewer.setHeaderLabels(["No activity yet."])

    def update_working_folder_display(self):
        folder_path = self.controller.working_folder
        if folder_path and os.path.isdir(folder_path): self.working_folder_display_text_label.setText(f"Working Folder: {folder_path}")
        else: self.working_folder_display_text_label.setText("Working Folder: <NOT SET>")
    
    def toggle_ui_elements(self, enable):
        for widget in [self.project_tree, self.edit_update_button, self.new_project_button, self.open_folder_button, self.preview_button, self.details_button, self.refresh_button]:
            widget.setEnabled(enable)
        if not enable: self.project_tree.clear(); QTreeWidgetItem(self.project_tree, ["", "Set working folder to view projects.", "", "", ""])
    
    def on_project_double_click(self, item): self.view_project_details()
    def get_selected_project_id(self):
        selected_item = self.project_tree.currentItem(); return selected_item.data(0, Qt.ItemDataRole.UserRole) if selected_item else None
    def create_new_project(self): self.controller.set_current_project_for_editing(None); self.navigate_request.emit("NewProjectP2_Department")
    def edit_selected_project(self):
        project_id = self.get_selected_project_id()
        if project_id: self.controller.set_current_project_for_editing(project_id); self.navigate_request.emit("NewProjectP2_Department")
        else: QMessageBox.warning(self, "Selection Required", "Please select a project to edit.")
    def view_project_details(self):
        project_id = self.get_selected_project_id()
        if project_id: self.controller.set_current_project_for_editing(project_id); self.navigate_request.emit("ProjectDetailsView")
        else: QMessageBox.warning(self, "Selection Required", "Please select a project to view details.")
    def preview_project_action(self):
        project_id = self.get_selected_project_id()
        if project_id: self.controller.set_current_project_for_editing(project_id); self.navigate_request.emit("ProjectCreationPreview")
        else: QMessageBox.warning(self, "Selection Required", "Please select a project to preview.")
    def open_project_folder_action(self):
        project_id = self.get_selected_project_id()
        project = next((p for p in self.controller.all_projects_data if p.get('id') == project_id), None) if project_id else None
        
        folder_path = project.get('projectFolderPath') if project else None

        # First, check if a path is stored and if that path actually exists as a directory
        if folder_path and os.path.isdir(folder_path):
            # Use the cross-platform Qt method to safely open the folder
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder_path))
        else:
            # If the folder doesn't exist, show a helpful warning instead of crashing
            QMessageBox.warning(self, "Folder Not Found",
                              f"The project folder could not be found at the expected location:\n{folder_path}\n\nIt may have been moved or deleted.")
# ========================================================================
# Class: NewProjectP2_Department to FulfillmentView are unchanged
# ========================================================================

class NewProjectP2_Department(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='departmentDetails')
        
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font()
        font.setPointSize(14)
        self.project_name_header_label.setFont(font)
        
        page_title_label = QLabel("DEPARTMENT DETAILS:")
        font = page_title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        page_title_label.setFont(font)
        
        content_layout.addWidget(self.project_name_header_label)
        content_layout.addWidget(page_title_label)
        content_layout.addSpacing(20)
        
        form_layout = QVBoxLayout()
        form_layout.setSpacing(15)
        
        # Department ComboBox
        dept_layout = QHBoxLayout()
        dept_label = QLabel("Select Department:")
        dept_label.setFixedWidth(180)
        dept_layout.addWidget(dept_label)
        self.department_combobox = QComboBox()
        self.department_combobox.currentTextChanged.connect(self._on_department_selected)
        dept_layout.addWidget(self.department_combobox)
        form_layout.addLayout(dept_layout)
        
        # Memo ID
        memo_layout = QHBoxLayout()
        memo_label = QLabel("Department Memo ID:")
        memo_label.setFixedWidth(180)
        memo_layout.addWidget(memo_label)
        self.memoId_entry = QLineEdit()
        memo_layout.addWidget(self.memoId_entry)
        form_layout.addLayout(memo_layout)
        
        # Memo Date
        memo_date_layout = QHBoxLayout()
        memo_date_label = QLabel("Memo Date:")
        memo_date_label.setFixedWidth(180)
        memo_date_layout.addWidget(memo_date_label)
        self.memoDate_edit = QDateEdit()
        self.memoDate_edit.setCalendarPopup(True)
        self.memoDate_edit.setDisplayFormat("yyyy-MM-dd")
        memo_date_layout.addWidget(self.memoDate_edit, 0, Qt.AlignmentFlag.AlignLeft)
        memo_date_layout.addStretch(1)
        form_layout.addLayout(memo_date_layout)
        
        content_layout.addLayout(form_layout)
        content_layout.addStretch(1)
        
        # CORRECTED NAVIGATION: Next button now goes to the Project Name page.
        self.main_layout.addLayout(self._create_navigation_buttons(back_page="HomeView", next_page_or_action="NewProjectP1"))

    def on_show(self):
        super().on_show()
        dept_details = self._get_section_data()
        self.department_combobox.blockSignals(True)
        self.department_combobox.clear()
        departments_from_db = utils.get_all_departments_from_db(self.controller.departments_db_path)
        self.department_combobox.addItem("<Select Department>")
        self.department_combobox.addItems([d['name'] for d in departments_from_db])
        self.department_combobox.blockSignals(False)
        current_dept_id = self.controller.current_project_data.get('departmentId')
        selected_dept_name = "<Select Department>"
        if current_dept_id:
            dept_info = utils.get_department_by_id(self.controller.departments_db_path, current_dept_id)
            if dept_info and dept_info.get('name'):
                selected_dept_name = dept_info['name']
        self.department_combobox.setCurrentText(selected_dept_name)
        self.memoId_entry.setText(dept_details.get('memoId', ''))
        memo_date_str = dept_details.get('memoDate', '')
        if memo_date_str:
            self.memoDate_edit.setDate(datetime.datetime.strptime(memo_date_str, "%Y-%m-%d").date())
        else:
            self.memoDate_edit.setDate(datetime.date.today())

    def _on_department_selected(self, selected_dept_name):
        dept_details = self._get_section_data()
        if selected_dept_name == "<Select Department>":
            dept_details['name'] = ""
            dept_details['address'] = ""
            self.controller.current_project_data['departmentId'] = None
            return
        all_depts = utils.get_all_departments_from_db(self.controller.departments_db_path)
        selected_dept = next((d for d in all_depts if d['name'] == selected_dept_name), None)
        if selected_dept:
            dept_details['name'] = selected_dept['name']
            dept_details['address'] = selected_dept['address']
            self.controller.current_project_data['departmentId'] = selected_dept['id']
        else:
            dept_details['name'] = ""
            dept_details['address'] = ""
            self.controller.current_project_data['departmentId'] = None

    def update_controller_project_data_from_form(self):
        dept_details = self._get_section_data()
        if dept_details:
            dept_details['memoId'] = self.memoId_entry.text().strip()
            dept_details['memoDate'] = self.memoDate_edit.date().toString("yyyy-MM-dd")


    
# ========================================================================
# Class 3: NewProjectP1
# ========================================================================

class NewProjectP1(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key=None)
        
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout, 1)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.project_name_header_label = QLabel("NEW PROJECT CREATION")
        font = self.project_name_header_label.font()
        font.setPointSize(18); font.setBold(True)
        self.project_name_header_label.setFont(font)
        
        content_layout.addWidget(self.project_name_header_label)
        content_layout.addSpacing(20)

        form_layout = QVBoxLayout(); form_layout.setSpacing(15)
        
        name_layout = QHBoxLayout()
        name_label = QLabel("Project Name:"); name_label.setFixedWidth(220)
        name_layout.addWidget(name_label)
        self.project_name_entry = QLineEdit()
        name_layout.addWidget(self.project_name_entry)
        form_layout.addLayout(name_layout)

        lead_layout = QHBoxLayout()
        lead_label = QLabel("Project Lead/Manager:"); lead_label.setFixedWidth(220)
        lead_layout.addWidget(lead_label)
        self.project_lead_entry = QLineEdit()
        lead_layout.addWidget(self.project_lead_entry)
        form_layout.addLayout(lead_layout)
        
        self.is_tender_checkbox = QCheckBox("This is a Tender-Based Project")
        self.is_limited_tender_checkbox = QCheckBox("This is a Limited Tender Project") # --- NEW ---
        
        # --- NEW: Ensure checkboxes are mutually exclusive ---
        self.is_tender_checkbox.toggled.connect(
            lambda checked: self.is_limited_tender_checkbox.setChecked(False) if checked else None
        )
        self.is_limited_tender_checkbox.toggled.connect(
            lambda checked: self.is_tender_checkbox.setChecked(False) if checked else None
        )

        form_layout.addWidget(self.is_tender_checkbox)
        form_layout.addWidget(self.is_limited_tender_checkbox) # --- NEW ---
        content_layout.addLayout(form_layout)
        
        self.main_layout.addLayout(
            self._create_navigation_buttons(
                back_page="NewProjectP2_Department", 
                next_page_or_action="NewProjectP2A_Enquiry"
            )
        )

    def on_show(self):
        super().on_show()
        if self.controller.current_project_data is None:
            self.controller.set_current_project_for_editing(None)
        
        project_data = self.controller.current_project_data

        self.project_name_entry.setText(project_data.get('projectName', ''))
        self.project_lead_entry.setText(project_data.get('projectLead', ''))

        # --- THIS IS THE FIX ---
        # We wrap the .get() calls with bool() to ensure that even if the value
        # is None, it gets converted to False, preventing the crash.
        is_tender = project_data.get('isTenderProject', False)
        is_limited = project_data.get('isLimitedTenderProject', False)

        self.is_tender_checkbox.setChecked(bool(is_tender))
        self.is_limited_tender_checkbox.setChecked(bool(is_limited))
        # --- END OF FIX ---
        self.project_name_entry.setFocus()

    def update_controller_project_data_from_form(self):
        if self.controller.current_project_data is None:
            self.controller.set_current_project_for_editing(None)
        
        self.controller.current_project_data['projectName'] = self.project_name_entry.text().strip()
        self.controller.current_project_data['projectLead'] = self.project_lead_entry.text().strip()
        self.controller.current_project_data['isTenderProject'] = self.is_tender_checkbox.isChecked()
        self.controller.current_project_data['isLimitedTenderProject'] = self.is_limited_tender_checkbox.isChecked() # --- NEW ---
        
    def handle_next(self, target_page):
        self.update_controller_project_data_from_form()
        project_name = self.controller.current_project_data.get('projectName', '').strip()
        if not project_name:
            QMessageBox.critical(self, "Validation Error", "Project Name cannot be empty to proceed.")
            return
        super().handle_next(target_page)
# ========================================================================
# Class 4: NewProjectP2A_Enquiry (New)
# ========================================================================

class NewProjectP2A_Enquiry(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='departmentEnquiryDetails')
        
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font()
        font.setPointSize(14)
        self.project_name_header_label.setFont(font)

        page_title_label = QLabel("DEPARTMENT ENQUIRY DOCUMENTS:")
        font = page_title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        page_title_label.setFont(font)
        
        content_layout.addWidget(self.project_name_header_label)
        content_layout.addWidget(page_title_label)
        content_layout.addSpacing(10)

        # --- Document Management ---
        doc_management_layout = QHBoxLayout()
        doc_management_layout.addWidget(QLabel("Enquiry Documents:"))
        doc_management_layout.addStretch(1)
        add_doc_button = QPushButton("Add Document(s)")
        add_doc_button.clicked.connect(self._add_enquiry_documents)
        remove_doc_button = QPushButton("Remove Selected")
        remove_doc_button.clicked.connect(self._remove_selected_enquiry_document)
        doc_management_layout.addWidget(add_doc_button)
        doc_management_layout.addWidget(remove_doc_button)
        content_layout.addLayout(doc_management_layout)

        self.enquiry_documents_tree = QTreeWidget()
        self.enquiry_documents_tree.setHeaderLabels(["File Name"])
        self.enquiry_documents_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.enquiry_documents_tree, 1)

        # --- CORRECTED NAVIGATION ---
        self.main_layout.addLayout(
            self._create_navigation_buttons(
                back_page="NewProjectP1",
                next_page_or_action=self.handle_next_logic
            )
        )

    def on_show(self):
        super().on_show()
        self._get_section_data()
        self.refresh_doc_tree()

    def refresh_doc_tree(self, doc_key_name=None):
        self.enquiry_documents_tree.clear()
        details = self._get_section_data()
        if 'documents' in details:
            for idx, doc_data in enumerate(details.get('documents', [])):
                if isinstance(doc_data, dict):
                    item = QTreeWidgetItem([doc_data.get('name', 'N/A')])
                    item.setData(0, Qt.ItemDataRole.UserRole, idx)
                    self.enquiry_documents_tree.addTopLevelItem(item)

    def _add_enquiry_documents(self):
        target_subfolder = SUBFOLDER_NAMES.get("departmentEnquiryDetails", "Dept_Enquiry_Docs")
        self._handle_document_selection('documents', None, target_subfolder, allow_multiple=True)

    def _remove_selected_enquiry_document(self):
        selected_items = self.enquiry_documents_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a document to remove.")
            return

        details = self._get_section_data()
        if not details or 'documents' not in details:
            return

        reply = QMessageBox.question(self, "Confirm Removal", 
                                     f"Are you sure you want to remove the selected {len(selected_items)} document reference(s)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        indices_to_remove = sorted([item.data(0, Qt.ItemDataRole.UserRole) for item in selected_items], reverse=True)
        docs_to_remove = [details['documents'][i] for i in indices_to_remove]
        
        for index in indices_to_remove:
            details['documents'].pop(index)

        reply_delete = QMessageBox.question(self, "Delete Files?",
                                            "Do you also want to delete the associated file(s) from the project folder?\nThis cannot be undone.",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply_delete == QMessageBox.StandardButton.Yes:
            project_folder = self.controller.current_project_data.get('projectFolderPath')
            if project_folder:
                for doc in docs_to_remove:
                    try:
                        file_path = Path(project_folder) / doc.get('path', '')
                        if file_path.exists() and file_path.is_file():
                            file_path.unlink()
                    except Exception as e:
                        QMessageBox.warning(self, "Deletion Warning", f"Could not delete physical file: {doc.get('name')}\n{e}")

        self.refresh_doc_tree()

    def handle_next_logic(self):
        """Overridden to handle conditional navigation based on tender status."""
        is_tender = self.controller.current_project_data.get('isTenderProject', False)
        is_limited_tender = self.controller.current_project_data.get('isLimitedTenderProject', False)
        
        if is_limited_tender:
            target_page = "LimitedTenderView"
        elif is_tender:
            target_page = "TenderManagementPage"
        else:
            target_page = "NewProjectP3_OEM"
            
        super().handle_next(target_page)

# ========================================================================
# NEW CLASS: TenderManagementPage
# ========================================================================

class TenderManagementPage(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='tenderDetails')
        
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        content_layout.setContentsMargins(10, 10, 10, 10)

        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font(); font.setPointSize(14)
        self.project_name_header_label.setFont(font)
        
        page_title_label = QLabel("TENDER & BIDDING DETAILS:")
        font = page_title_label.font(); font.setPointSize(18); font.setBold(True)
        page_title_label.setFont(font)
        
        content_layout.addWidget(self.project_name_header_label)
        content_layout.addWidget(page_title_label)
        
        main_tabs = QTabWidget()
        content_layout.addWidget(main_tabs, 1)

        # --- Tab 1: Tender Documents ---
        docs_tab = QWidget()
        docs_layout = QVBoxLayout(docs_tab)
        docs_layout.addWidget(self.create_doc_tab("tenderNoticeDocs", "Tender Notice Documents"))
        main_tabs.addTab(docs_tab, "Tender Documents")

        # --- Tab 2: Bidders Management ---
        bidders_tab = QWidget()
        bidders_layout = QVBoxLayout(bidders_tab)
        bidder_entry_layout = QHBoxLayout()
        bidder_entry_layout.addWidget(QLabel("New Bidder Name:"))
        self.new_bidder_name_entry = QLineEdit()
        bidder_entry_layout.addWidget(self.new_bidder_name_entry)
        add_bidder_button = QPushButton("Add Bidder")
        add_bidder_button.clicked.connect(self.add_bidder)
        bidder_entry_layout.addWidget(add_bidder_button)
        bidders_layout.addLayout(bidder_entry_layout)
        bidders_splitter = QHBoxLayout()
        self.bidders_list_widget = QTreeWidget()
        self.bidders_list_widget.setHeaderLabels(["Bidders"])
        self.bidders_list_widget.itemSelectionChanged.connect(self.on_bidder_selected)
        bidders_splitter.addWidget(self.bidders_list_widget, 1)
        
        self.bidder_docs_widget = self._create_bidder_doc_manager()
        self.bidder_docs_widget.setEnabled(False)
        
        bidders_splitter.addWidget(self.bidder_docs_widget, 2)
        bidders_layout.addLayout(bidders_splitter)
        main_tabs.addTab(bidders_tab, "Bidders Management")

        # --- Tab 3: Bid Qualification ---
        bid_qualification_tab = QWidget()
        bid_qualification_layout = QVBoxLayout(bid_qualification_tab)
        qualification_sub_tabs = QTabWidget()
        qualification_sub_tabs.addTab(self._create_general_eligibility_tab(), "General Eligibility")
        qualification_sub_tabs.addTab(self._create_technical_compliance_tab(), "Technical Compliance")
        qualification_sub_tabs.addTab(self._create_marks_distribution_tab(), "Marks Distribution")
        bid_qualification_layout.addWidget(qualification_sub_tabs)
        main_tabs.addTab(bid_qualification_tab, "Bid Qualification")

        # --- Tab 4: Qualified Bidder ---
        qualified_bidder_tab = QWidget()
        qualified_bidder_layout = QVBoxLayout(qualified_bidder_tab)
        qualified_bidder_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        qualified_layout = QHBoxLayout()
        qualified_layout.addWidget(QLabel("<b>Select Qualified Bidder:</b>"))
        self.qualified_bidder_combo = QComboBox()
        qualified_layout.addWidget(self.qualified_bidder_combo, 1)
        qualified_bidder_layout.addLayout(qualified_layout)
        main_tabs.addTab(qualified_bidder_tab, "Qualified Bidder")

        # --- Navigation ---
        self.main_layout.addLayout(
            self._create_navigation_buttons(
                back_page="NewProjectP2A_Enquiry",
                next_page_or_action="NewProjectP3_OEM"
            )
        )
    
    def _create_general_eligibility_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.eligibility_table = QTableWidget(0, 2)
        self.eligibility_table.setWordWrap(True)
        layout.addWidget(self.eligibility_table)
        buttons = QHBoxLayout()
        add_btn = QPushButton("Add Criteria"); add_btn.clicked.connect(lambda: self._add_qualification_row(self.eligibility_table, "eligibility"))
        rem_btn = QPushButton("Remove Selected Criteria"); rem_btn.clicked.connect(lambda: self._remove_qualification_row(self.eligibility_table))
        buttons.addStretch(); buttons.addWidget(add_btn); buttons.addWidget(rem_btn)
        layout.addLayout(buttons)
        return widget

    def _create_technical_compliance_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.compliance_table = QTableWidget(0, 2)
        self.compliance_table.setWordWrap(True)
        self.compliance_table.setItemDelegate(TextEditDelegate(self.compliance_table))
        layout.addWidget(self.compliance_table)
        buttons = QHBoxLayout()
        add_btn = QPushButton("Add Specification"); add_btn.clicked.connect(lambda: self._add_qualification_row(self.compliance_table, "compliance"))
        rem_btn = QPushButton("Remove Selected Specification"); rem_btn.clicked.connect(lambda: self._remove_qualification_row(self.compliance_table))
        buttons.addStretch(); buttons.addWidget(add_btn); buttons.addWidget(rem_btn)
        layout.addLayout(buttons)
        return widget
        
    def _create_marks_distribution_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.marks_table = QTableWidget(0, 1)
        self.marks_table.setWordWrap(True)
        self.marks_table.setItemDelegate(TextEditDelegate(self.marks_table))
        layout.addWidget(self.marks_table)
        buttons = QHBoxLayout()
        add_btn = QPushButton("Add Criteria"); add_btn.clicked.connect(lambda: self._add_qualification_row(self.marks_table, "marks"))
        rem_btn = QPushButton("Remove Selected Criteria"); rem_btn.clicked.connect(lambda: self._remove_qualification_row(self.marks_table))
        buttons.addStretch(); buttons.addWidget(add_btn); buttons.addWidget(rem_btn)
        layout.addLayout(buttons)
        return widget

    def _add_qualification_row(self, table_widget, type):
        row_position = table_widget.rowCount()
        table_widget.insertRow(row_position)
        table_widget.resizeRowsToContents()

    def _remove_qualification_row(self, table_widget):
        current_row = table_widget.currentRow()
        if current_row >= 0:
            table_widget.removeRow(current_row)

    def _rebuild_bid_qualification_tables(self):
        details = self._get_section_data()
        bidders = details.get('bidders', [])
        bidder_names = [b.get('name', '') for b in bidders]

        eligibility_headers = ["Description", "Eligibility Criteria"] + bidder_names
        self.eligibility_table.setColumnCount(len(eligibility_headers))
        self.eligibility_table.setHorizontalHeaderLabels(eligibility_headers)
        self.eligibility_table.setItemDelegateForColumn(0, TextEditDelegate(self.eligibility_table))
        self.eligibility_table.setItemDelegateForColumn(1, TextEditDelegate(self.eligibility_table))
        self.eligibility_table.setRowCount(0)
        for i, criterion in enumerate(details.get('generalEligibility', [])):
            self.eligibility_table.insertRow(i)
            self.eligibility_table.setItem(i, 0, QTableWidgetItem(criterion.get('description', '')))
            self.eligibility_table.setItem(i, 1, QTableWidgetItem(criterion.get('criteria', '')))
            for j, bidder in enumerate(bidders):
                combo = QComboBox(); combo.addItems(["", "Yes", "No"])
                response = bidder.get('evaluation', {}).get('eligibility', {}).get(str(i), '')
                combo.setCurrentText(response)
                self.eligibility_table.setCellWidget(i, 2 + j, combo)

        compliance_headers = ["Description of Service", "Tender Specification"] + bidder_names
        self.compliance_table.setColumnCount(len(compliance_headers))
        self.compliance_table.setHorizontalHeaderLabels(compliance_headers)
        self.compliance_table.setRowCount(0)
        for i, criterion in enumerate(details.get('technicalCompliance', [])):
            self.compliance_table.insertRow(i)
            self.compliance_table.setItem(i, 0, QTableWidgetItem(criterion.get('description', '')))
            self.compliance_table.setItem(i, 1, QTableWidgetItem(criterion.get('tenderSpec', '')))
            for j, bidder in enumerate(bidders):
                response = bidder.get('evaluation', {}).get('compliance', {}).get(str(i), '')
                self.compliance_table.setItem(i, 2 + j, QTableWidgetItem(response))

        marks_headers = ["Description", "Max Marks"] + bidder_names
        self.marks_table.setColumnCount(len(marks_headers))
        self.marks_table.setHorizontalHeaderLabels(marks_headers)
        self.marks_table.setRowCount(0)
        for i, criterion in enumerate(details.get('marksDistribution', [])):
            self.marks_table.insertRow(i)
            self.marks_table.setItem(i, 0, QTableWidgetItem(criterion.get('description', '')))
            self.marks_table.setItem(i, 1, QTableWidgetItem(str(criterion.get('maxMarks', ''))))
            for j, bidder in enumerate(bidders):
                response = bidder.get('evaluation', {}).get('marks', {}).get(str(i), '')
                self.marks_table.setItem(i, 2 + j, QTableWidgetItem(response))

        self.eligibility_table.resizeRowsToContents()
        self.compliance_table.resizeRowsToContents()
        self.marks_table.resizeRowsToContents()

    def _save_bid_qualification_tables(self):
        details = self._get_section_data()
        bidders = details.get('bidders', [])

        eligibility_criteria = []
        for row in range(self.eligibility_table.rowCount()):
            eligibility_criteria.append({
                'description': self.eligibility_table.item(row, 0).text() if self.eligibility_table.item(row, 0) else '',
                'criteria': self.eligibility_table.item(row, 1).text() if self.eligibility_table.item(row, 1) else ''
            })
            for j, bidder in enumerate(bidders):
                combo = self.eligibility_table.cellWidget(row, 2 + j)
                if combo:
                    bidder.setdefault('evaluation', {}).setdefault('eligibility', {})[str(row)] = combo.currentText()
        details['generalEligibility'] = eligibility_criteria
        
        compliance_criteria = []
        for row in range(self.compliance_table.rowCount()):
            compliance_criteria.append({
                'description': self.compliance_table.item(row, 0).text() if self.compliance_table.item(row, 0) else '',
                'tenderSpec': self.compliance_table.item(row, 1).text() if self.compliance_table.item(row, 1) else ''
            })
            for j, bidder in enumerate(bidders):
                item = self.compliance_table.item(row, 2 + j)
                if item:
                    bidder.setdefault('evaluation', {}).setdefault('compliance', {})[str(row)] = item.text()
        details['technicalCompliance'] = compliance_criteria

        marks_criteria = []
        for row in range(self.marks_table.rowCount()):
            marks_criteria.append({
                'description': self.marks_table.item(row, 0).text() if self.marks_table.item(row, 0) else '',
                'maxMarks': self.marks_table.item(row, 1).text() if self.marks_table.item(row, 1) else ''
            })
            for j, bidder in enumerate(bidders):
                item = self.marks_table.item(row, 2 + j)
                if item:
                    bidder.setdefault('evaluation', {}).setdefault('marks', {})[str(row)] = item.text()
        details['marksDistribution'] = marks_criteria

    def _create_bidder_doc_manager(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<b>Selected Bidder's Documents</b>"))
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        add_button = QPushButton("Add Document(s)"); add_button.clicked.connect(self._add_document_to_selected_bidder)
        remove_button = QPushButton("Remove Selected"); remove_button.clicked.connect(self._remove_document_from_selected_bidder)
        button_layout.addWidget(add_button); button_layout.addWidget(remove_button)
        layout.addLayout(button_layout)
        
        self.biddersDocs_tree = QTreeWidget(); self.biddersDocs_tree.setHeaderLabels(["File Name"])
        self.biddersDocs_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.biddersDocs_tree)
        return widget

    def _add_document_to_selected_bidder(self):
        selected_bidder = self.get_selected_bidder()
        if not selected_bidder:
            QMessageBox.warning(self, "Selection Error", "Please select a bidder before adding documents.")
            return

        filepaths, _ = QFileDialog.getOpenFileNames(self, "Select one or more documents")
        if not filepaths: return

        project_main_folder_str = self.controller.current_project_data.get('projectFolderPath')
        if not project_main_folder_str:
            QMessageBox.critical(self, "Error", "Project folder path not found.")
            return

        bidder_name = selected_bidder.get('name', 'Unnamed_Bidder')
        safe_bidder_name = "".join(c for c in bidder_name if c.isalnum() or c in (' ', '_', '-')).rstrip().replace(" ", "_")
        if not safe_bidder_name:
            safe_bidder_name = f"bidder_{uuid.uuid4().hex[:8]}"

        base_bidders_path = SUBFOLDER_NAMES.get("biddersDocs", "Tender_Documents/3_Bidders")
        target_path = Path(project_main_folder_str) / base_bidders_path / safe_bidder_name
        target_path.mkdir(parents=True, exist_ok=True)
            
        docs_list_ref = selected_bidder.setdefault('docs', [])
        
        for fp_str in filepaths:
            original_file = Path(fp_str)
            destination_path = target_path / original_file.name
            try:
                shutil.copy2(original_file, destination_path)
                relative_path = destination_path.relative_to(project_main_folder_str)
                new_doc_data = {'name': original_file.name, 'path': str(relative_path), 'type': 'project_file'}
                docs_list_ref.append(new_doc_data)
            except Exception as e:
                QMessageBox.critical(self, "File Copy Error", f"Could not copy file: {e}")
        
        self.refresh_doc_tree('biddersDocs')

    def _remove_document_from_selected_bidder(self):
        selected_bidder = self.get_selected_bidder()
        selected_doc_items = self.biddersDocs_tree.selectedItems()

        if not selected_bidder or not selected_doc_items:
            QMessageBox.warning(self, "Selection Error", "Please select a bidder and a document to remove.")
            return

        reply = QMessageBox.question(self, "Confirm Removal", "Are you sure you want to remove the selected document(s)?")
        if reply == QMessageBox.StandardButton.No: return

        indices_to_remove = sorted([item.data(0, Qt.ItemDataRole.UserRole) for item in selected_doc_items], reverse=True)
        
        for index in indices_to_remove:
            selected_bidder['docs'].pop(index)
        
        self.refresh_doc_tree('biddersDocs')

    def create_doc_tab(self, doc_key, label_text):
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.addWidget(QLabel(f"<b>{label_text}</b>"))
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        add_button = QPushButton("Add Document(s)")
        remove_button = QPushButton("Remove Selected")
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        layout.addLayout(button_layout)
        
        tree = QTreeWidget(); tree.setHeaderLabels(["File Name"])
        tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(tree)
        
        setattr(self, f"{doc_key}_tree", tree)
        target_subfolder = SUBFOLDER_NAMES.get(doc_key, "Tender_Documents")
        add_button.clicked.connect(lambda: self._handle_document_selection(doc_key, None, target_subfolder, allow_multiple=True))
        remove_button.clicked.connect(lambda: self.remove_document(doc_key))
        return tab_widget

    def on_show(self):
        super().on_show()
        self.refresh_all_doc_trees()
        self.refresh_bidders_list()
        self._rebuild_bid_qualification_tables()
        details = self._get_section_data()
        self.qualified_bidder_combo.setCurrentText(details.get('qualifiedBidder', ''))

    def update_controller_project_data_from_form(self):
        details = self._get_section_data()
        if details:
            details['qualifiedBidder'] = self.qualified_bidder_combo.currentText()
            self._save_bid_qualification_tables()

    def refresh_doc_tree(self, doc_key):
        tree = getattr(self, f"{doc_key}_tree", None)
        if not tree: return
        tree.clear()
        
        docs_list = []
        if doc_key == "biddersDocs":
            selected_bidder = self.get_selected_bidder()
            if selected_bidder:
                docs_list = selected_bidder.get('docs', [])
        else:
            details = self._get_section_data()
            docs_list = details.get(doc_key, [])
            
        for idx, doc_data in enumerate(docs_list):
            item = QTreeWidgetItem([doc_data.get('name', 'N/A')])
            item.setData(0, Qt.ItemDataRole.UserRole, idx)
            tree.addTopLevelItem(item)

    def refresh_all_doc_trees(self):
        self.refresh_doc_tree("tenderNoticeDocs")
        self.refresh_doc_tree("biddersDocs")

    def refresh_bidders_list(self):
        self.bidders_list_widget.clear()
        self.qualified_bidder_combo.clear()
        details = self._get_section_data()
        self.qualified_bidder_combo.addItem("")
        for idx, bidder in enumerate(details.get('bidders', [])):
            item = QTreeWidgetItem([bidder['name']])
            item.setData(0, Qt.ItemDataRole.UserRole, idx)
            self.bidders_list_widget.addTopLevelItem(item)
            self.qualified_bidder_combo.addItem(bidder['name'])

    def on_bidder_selected(self):
        self.bidder_docs_widget.setEnabled(len(self.bidders_list_widget.selectedItems()) > 0)
        self.refresh_doc_tree("biddersDocs")

    def get_selected_bidder(self):
        selected_items = self.bidders_list_widget.selectedItems()
        if not selected_items: return None
        idx = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
        details = self._get_section_data()
        return details.get('bidders', [])[idx]

    def add_bidder(self):
        name = self.new_bidder_name_entry.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Bidder name cannot be empty.")
            return
        details = self._get_section_data()
        bidders = details.setdefault('bidders', [])
        bidders.append({'name': name, 'docs': [], 'evaluation': {}})
        self.new_bidder_name_entry.clear()
        self.refresh_bidders_list()
        self._rebuild_bid_qualification_tables()

    def remove_document(self, doc_key):
        QMessageBox.information(self, "Info", "Document removal logic is not yet implemented.")


# ========================================================================
# NEW CLASS: LimitedTenderView
# ========================================================================
# ========================================================================
# CLASS: LimitedTenderView (REVISED)
# ========================================================================
class LimitedTenderView(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='limitedTenderDetails')
        
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        content_layout.setContentsMargins(10, 10, 10, 10)

        # --- Header ---
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font(); font.setPointSize(14); self.project_name_header_label.setFont(font)
        page_title_label = QLabel("LIMITED TENDER: COMPARATIVE STATEMENT")
        font = page_title_label.font(); font.setPointSize(18); font.setBold(True); page_title_label.setFont(font)
        
        content_layout.addWidget(self.project_name_header_label)
        content_layout.addWidget(page_title_label, 0, Qt.AlignmentFlag.AlignCenter)

        # --- NEW: Pre-bid / Tender Notice Document Section ---
        notice_frame = QFrame(); notice_frame.setObjectName("CardFrame")
        notice_layout = QVBoxLayout(notice_frame)
        notice_layout.addWidget(QLabel("<b>Pre-Bid / Tender Notice Documents</b>"))
        
        notice_button_layout = QHBoxLayout()
        add_notice_button = QPushButton("Add Document(s)"); add_notice_button.clicked.connect(self._add_tender_notice_docs)
        remove_notice_button = QPushButton("Remove Selected"); remove_notice_button.clicked.connect(self._remove_tender_notice_docs)
        notice_button_layout.addStretch(); notice_button_layout.addWidget(add_notice_button); notice_button_layout.addWidget(remove_notice_button)
        notice_layout.addLayout(notice_button_layout)

        self.notice_docs_tree = QTreeWidget()
        self.notice_docs_tree.setHeaderLabels(["File Name"])
        self.notice_docs_tree.itemDoubleClicked.connect(self._open_document_link)
        notice_layout.addWidget(self.notice_docs_tree)
        content_layout.addWidget(notice_frame)

        # --- Main Content Splitter ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(main_splitter, 1)

        # --- Left Panel: Bidders List ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        entry_frame = QFrame(); entry_frame.setObjectName("CardFrame")
        entry_layout = QGridLayout(entry_frame)
        self.bidder_name_entry = QLineEdit(placeholderText="Bidder Name")
        self.bidder_price_entry = QLineEdit(placeholderText="Quoted Price (e.g., 15000.00)")
        add_bidder_button = QPushButton("Add Bidder"); add_bidder_button.clicked.connect(self.add_bidder)
        entry_layout.addWidget(QLabel("New Bidder:"), 0, 0); entry_layout.addWidget(self.bidder_name_entry, 0, 1)
        entry_layout.addWidget(self.bidder_price_entry, 0, 2); entry_layout.addWidget(add_bidder_button, 0, 3)
        left_layout.addWidget(entry_frame)

        self.bidders_table = QTableWidget()
        self.bidders_table.setColumnCount(2)
        self.bidders_table.setHorizontalHeaderLabels(["Bidder Name", "Quoted Price (INR)"])
        self.bidders_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.bidders_table.setColumnWidth(1, 180) # <-- INCREASED COLUMN WIDTH
        self.bidders_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bidders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bidders_table.itemSelectionChanged.connect(self._on_bidder_selected)
        left_layout.addWidget(self.bidders_table)
        
        action_layout = QHBoxLayout()
        self.remove_bidder_button = QPushButton("Remove Selected Bidder"); self.remove_bidder_button.clicked.connect(self.remove_selected_bidder)
        self.select_winner_button = QPushButton("Select Lowest as Winner"); self.select_winner_button.setObjectName("FinishButton"); self.select_winner_button.clicked.connect(self.select_winner)
        action_layout.addWidget(self.remove_bidder_button)
        action_layout.addStretch()
        action_layout.addWidget(self.select_winner_button)
        left_layout.addLayout(action_layout)

        # --- Right Panel: Document Viewer ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.docs_label = QLabel("Documents for: <None>"); self.docs_label.setObjectName("FormTitle")
        font = self.docs_label.font(); font.setPointSize(12); self.docs_label.setFont(font)
        
        doc_button_layout = QHBoxLayout()
        add_doc_button = QPushButton("Add Document(s)"); add_doc_button.clicked.connect(self._add_document_to_bidder)
        remove_doc_button = QPushButton("Remove Selected"); remove_doc_button.clicked.connect(self._remove_document_from_bidder)
        doc_button_layout.addStretch(); doc_button_layout.addWidget(add_doc_button); doc_button_layout.addWidget(remove_doc_button)

        self.bidder_docs_tree = QTreeWidget()
        self.bidder_docs_tree.setHeaderHidden(True)
        self.bidder_docs_tree.itemDoubleClicked.connect(self._open_document_link)

        right_layout.addWidget(self.docs_label)
        right_layout.addLayout(doc_button_layout)
        right_layout.addWidget(self.bidder_docs_tree, 1)
        
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([600, 300])
        self.doc_panel = right_panel

        # --- Navigation ---
        self.main_layout.addLayout(self._create_navigation_buttons(back_page="NewProjectP2A_Enquiry", next_page_or_action="NewProjectP3_OEM"))

    def on_show(self):
        super().on_show()
        self._get_section_data()
        self.refresh_bidders_table()
        self._refresh_tender_notice_tree() # <-- NEW
        self._on_bidder_selected()

    def add_bidder(self):
        name = self.bidder_name_entry.text().strip()
        price_str = self.bidder_price_entry.text().strip()
        if not name or not price_str:
            QMessageBox.warning(self, "Input Error", "Both bidder name and price are required.")
            return
        try:
            price = float(price_str)
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter a valid number for the price.")
            return
        details = self._get_section_data()
        details.setdefault('bidders', []).append({'name': name, 'price': price, 'docs': []})
        self.bidder_name_entry.clear(); self.bidder_price_entry.clear()
        self.refresh_bidders_table()
    
    def remove_selected_bidder(self):
        selected_row = self.bidders_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a bidder to remove.")
            return
        details = self._get_section_data()
        details['bidders'].pop(selected_row)
        self.refresh_bidders_table()
    
    def select_winner(self):
        details = self._get_section_data()
        bidders = details.get('bidders', [])
        if not bidders:
            QMessageBox.warning(self, "Error", "There are no bidders to select from.")
            return
        lowest_bidder = min(bidders, key=lambda x: x['price'])
        details['winner'] = lowest_bidder['name']
        oem_details = self.controller.current_project_data.get('oemVendorDetails', {})
        oem_details['vendorName'] = lowest_bidder['name']
        oem_details['price'] = str(lowest_bidder['price'])
        QMessageBox.information(self, "Winner Selected", f"'{lowest_bidder['name']}' has been selected as the winner with the lowest price of {lowest_bidder['price']:.2f} INR.")
        self.refresh_bidders_table()

    def refresh_bidders_table(self):
        details = self._get_section_data()
        bidders = details.get('bidders', [])
        winner_name = details.get('winner')
        self.bidders_table.setRowCount(len(bidders))
        for row, bidder in enumerate(bidders):
            name_item = QTableWidgetItem(bidder['name'])
            price_item = QTableWidgetItem(f"{bidder['price']:.2f}")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if bidder['name'] == winner_name:
                font = name_item.font(); font.setBold(True); name_item.setFont(font); price_item.setFont(font)
                name_item.setForeground(QColor("darkgreen")); price_item.setForeground(QColor("darkgreen"))
            self.bidders_table.setItem(row, 0, name_item)
            self.bidders_table.setItem(row, 1, price_item)

    def _get_selected_bidder(self):
        selected_row = self.bidders_table.currentRow()
        if selected_row < 0: return None
        details = self._get_section_data()
        return details['bidders'][selected_row]

    def _on_bidder_selected(self):
        bidder = self._get_selected_bidder()
        is_bidder_selected = bidder is not None
        self.doc_panel.setEnabled(is_bidder_selected)
        if is_bidder_selected:
            self.docs_label.setText(f"Documents for: {bidder['name']}")
            self._refresh_bidder_document_tree()
        else:
            self.docs_label.setText("Documents for: <None>")
            self.bidder_docs_tree.clear()
    
    def _refresh_bidder_document_tree(self):
        self.bidder_docs_tree.clear()
        bidder = self._get_selected_bidder()
        if not bidder: return
        for doc in bidder.get('docs', []):
            item = QTreeWidgetItem([doc['name']])
            item.setData(0, Qt.ItemDataRole.UserRole, doc)
            item.setForeground(0, QBrush(QColor("#0969DA")))
            item.setToolTip(0, "Double-click to open file")
            self.bidder_docs_tree.addTopLevelItem(item)

    def _add_document_to_bidder(self):
        bidder = self._get_selected_bidder()
        if not bidder:
            QMessageBox.warning(self, "Selection Error", "Please select a bidder first.")
            return
        target_subfolder = SUBFOLDER_NAMES.get("limitedTenderBidders", "Limited_Tender_Documents")
        bidder_folder = "".join(c for c in bidder['name'] if c.isalnum() or c in (' ', '_', '-')).rstrip()
        full_target_subfolder = Path(target_subfolder) / bidder_folder
        self._handle_document_selection('docs', None, str(full_target_subfolder), allow_multiple=True, target_dict=bidder)
        QTimer.singleShot(100, self._refresh_bidder_document_tree)

    def _remove_document_from_bidder(self):
        bidder = self._get_selected_bidder()
        selected_doc_item = self.bidder_docs_tree.currentItem()
        if not bidder or not selected_doc_item:
            QMessageBox.warning(self, "Selection Error", "Please select a bidder and a document to remove.")
            return
        doc_to_remove = selected_doc_item.data(0, Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Confirm Removal", f"Are you sure you want to remove the reference to '{doc_to_remove['name']}'?")
        if reply == QMessageBox.StandardButton.Yes:
            bidder['docs'].remove(doc_to_remove)
            if QMessageBox.question(self, "Delete File?", "Do you also want to delete the actual file?") == QMessageBox.StandardButton.Yes:
                project_folder = self.controller.current_project_data.get('projectFolderPath')
                if project_folder and doc_to_remove.get('path'):
                    try:
                        (Path(project_folder) / doc_to_remove['path']).unlink(missing_ok=True)
                    except Exception as e:
                        QMessageBox.warning(self, "Deletion Error", f"Could not delete file: {e}")
            self._refresh_bidder_document_tree()

    def _open_document_link(self, item, column):
        doc_data = item.data(0, Qt.ItemDataRole.UserRole)
        project_folder = self.controller.current_project_data.get('projectFolderPath')
        if doc_data and project_folder and doc_data.get('path'):
            full_path = Path(project_folder) / doc_data['path']
            if full_path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))
            else:
                QMessageBox.warning(self, "File Not Found", f"Could not find file: {full_path}")
    
    # --- NEW METHODS FOR TENDER NOTICE DOCS ---
    def _refresh_tender_notice_tree(self):
        self.notice_docs_tree.clear()
        details = self._get_section_data()
        for doc in details.get('tenderNoticeDocs', []):
            item = QTreeWidgetItem([doc['name']])
            item.setData(0, Qt.ItemDataRole.UserRole, doc)
            item.setForeground(0, QBrush(QColor("#0969DA")))
            item.setToolTip(0, "Double-click to open file")
            self.notice_docs_tree.addTopLevelItem(item)

    def _add_tender_notice_docs(self):
        target_subfolder = SUBFOLDER_NAMES.get("limitedTenderBidders", "Limited_Tender_Documents")
        # Save notice docs in the root of the limited tender folder
        self._handle_document_selection('tenderNoticeDocs', None, target_subfolder, allow_multiple=True)
        QTimer.singleShot(100, self._refresh_tender_notice_tree) # Use a timer to allow file dialog to close

    def _remove_tender_notice_docs(self):
        selected_item = self.notice_docs_tree.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Selection Error", "Please select a notice document to remove.")
            return
        
        doc_to_remove = selected_item.data(0, Qt.ItemDataRole.UserRole)
        details = self._get_section_data()

        reply = QMessageBox.question(self, "Confirm Removal", f"Are you sure you want to remove '{doc_to_remove['name']}'?")
        if reply == QMessageBox.StandardButton.Yes:
            details['tenderNoticeDocs'].remove(doc_to_remove)
            if QMessageBox.question(self, "Delete File?", "Do you also want to delete the actual file?") == QMessageBox.StandardButton.Yes:
                project_folder = self.controller.current_project_data.get('projectFolderPath')
                if project_folder and doc_to_remove.get('path'):
                    try:
                        (Path(project_folder) / doc_to_remove['path']).unlink(missing_ok=True)
                    except Exception as e:
                        QMessageBox.warning(self, "Deletion Error", f"Could not delete file: {e}")
            self._refresh_tender_notice_tree()

# ========================================================================
# Class 5: NewProjectP3_OEM (Corrected)
# ========================================================================

# In ui/pages.py

class NewProjectP3_OEM(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='oemVendorDetails')
        
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font()
        font.setPointSize(14)
        self.project_name_header_label.setFont(font)

        page_title_label = QLabel("OEM-VENDOR DETAILS:")
        font = page_title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        page_title_label.setFont(font)
        
        content_layout.addWidget(self.project_name_header_label)
        content_layout.addWidget(page_title_label)
        content_layout.addSpacing(10)
        
        form_layout = QVBoxLayout()
        form_layout.setSpacing(15)
        self.entries = {}

        field_defs = [("OEM Name:", "oemName"), ("Vendor Name:", "vendorName"), ("Price Provided by OEM (Rs):", "price")]
        for label_text, key in field_defs:
            field_layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(200)
            field_layout.addWidget(label)
            entry = QLineEdit()
            self.entries[key] = entry
            field_layout.addWidget(entry)
            form_layout.addLayout(field_layout)

        date_layout = QHBoxLayout()
        date_label = QLabel("Date:")
        date_label.setFixedWidth(200)
        date_layout.addWidget(date_label)
        self.entries['date'] = QDateEdit()
        self.entries['date'].setCalendarPopup(True)
        self.entries['date'].setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self.entries['date'], 0, Qt.AlignmentFlag.AlignLeft)
        date_layout.addStretch(1)
        form_layout.addLayout(date_layout)
        
        content_layout.addLayout(form_layout)
        content_layout.addSpacing(10)

        doc_management_layout = QHBoxLayout()
        doc_management_layout.addWidget(QLabel("OEM/Vendor Documents:"))
        doc_management_layout.addStretch(1)
        add_doc_button = QPushButton("Add Document(s)")
        add_doc_button.clicked.connect(self._add_oem_documents)
        remove_doc_button = QPushButton("Remove Selected")
        remove_doc_button.clicked.connect(self._remove_selected_oem_document)
        doc_management_layout.addWidget(add_doc_button)
        doc_management_layout.addWidget(remove_doc_button)
        content_layout.addLayout(doc_management_layout)

        self.oem_documents_tree = QTreeWidget()
        self.oem_documents_tree.setHeaderLabels(["File Name"])
        self.oem_documents_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        content_layout.addWidget(self.oem_documents_tree, 1)
        
        # Initialize an empty layout for navigation buttons
        self.nav_layout = QHBoxLayout()

    def on_show(self):
        super().on_show()
        oem_details = self._get_section_data()
        
        project_data = self.controller.current_project_data
        is_tender = project_data.get('isTenderProject', False)
        is_limited_tender = project_data.get('isLimitedTenderProject', False)
        
        # Determine the correct previous page for the "Back" button
        if is_limited_tender:
            back_page = "LimitedTenderView"
        elif is_tender:
            back_page = "TenderManagementPage"
        else:
            back_page = "NewProjectP1"

        # Autofill vendor and price if a winner was selected, and make fields read-only
        self.entries['vendorName'].setReadOnly(False)
        self.entries['vendorName'].setToolTip("")
        self.entries['price'].setReadOnly(False)
        self.entries['price'].setToolTip("")

        if is_limited_tender:
            limited_tender_winner = project_data.get('limitedTenderDetails', {}).get('winner')
            if limited_tender_winner:
                self.entries['vendorName'].setText(oem_details.get('vendorName', ''))
                self.entries['price'].setText(str(oem_details.get('price', '')))
                self.entries['vendorName'].setReadOnly(True)
                self.entries['vendorName'].setToolTip("Vendor auto-filled from limited tender winner.")
                self.entries['price'].setReadOnly(True)
                self.entries['price'].setToolTip("Price auto-filled from limited tender winner.")
        elif is_tender:
            qualified_bidder = project_data.get('tenderDetails', {}).get('qualifiedBidder', '')
            if qualified_bidder:
                oem_details['vendorName'] = qualified_bidder
                self.entries['vendorName'].setReadOnly(True)
                self.entries['vendorName'].setToolTip("Vendor auto-filled from qualified bidder.")

        # Re-create navigation buttons with the correct back page target
        while self.nav_layout.count():
            child = self.nav_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.main_layout.removeItem(self.nav_layout)
        self.nav_layout = self._create_navigation_buttons(
            back_page=back_page,
            next_page_or_action="NewProjectP4_ProposalOrder"
        )
        self.main_layout.addLayout(self.nav_layout)
        
        # Populate form fields with data
        for key, widget in self.entries.items():
            value = oem_details.get(key, '')
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QDateEdit):
                if value:
                    try:
                        widget.setDate(datetime.datetime.strptime(value, "%Y-%m-%d").date())
                    except ValueError:
                        widget.setDate(datetime.date.today())
                else:
                    widget.setDate(datetime.date.today())
        self.refresh_doc_tree()

    def refresh_doc_tree(self, doc_key_name=None):
        self.oem_documents_tree.clear()
        oem_details = self._get_section_data()
        if oem_details and 'documents' in oem_details:
            for idx, doc_data in enumerate(oem_details.get('documents', [])):
                if isinstance(doc_data, dict):
                    item = QTreeWidgetItem([doc_data.get('name', 'N/A')])
                    item.setData(0, Qt.ItemDataRole.UserRole, idx)
                    self.oem_documents_tree.addTopLevelItem(item)

    def _add_oem_documents(self):
        target_subfolder = SUBFOLDER_NAMES.get(self.page_data_key, "Misc_Documents")
        self._handle_document_selection('documents', None, target_subfolder, allow_multiple=True)

    def _remove_selected_oem_document(self):
        selected_items = self.oem_documents_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a document to remove.")
            return

        oem_details = self._get_section_data()
        if not oem_details or 'documents' not in oem_details:
            return

        reply = QMessageBox.question(self, "Confirm Removal", 
                                     f"Are you sure you want to remove the selected {len(selected_items)} document reference(s)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        indices_to_remove = sorted([item.data(0, Qt.ItemDataRole.UserRole) for item in selected_items], reverse=True)
        docs_to_remove = [oem_details['documents'][i] for i in indices_to_remove]
        
        for index in indices_to_remove:
            oem_details['documents'].pop(index)

        reply_delete = QMessageBox.question(self, "Delete Files?",
                                            "Do you also want to delete the associated file(s) from the project folder?\nThis cannot be undone.",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply_delete == QMessageBox.StandardButton.Yes:
            project_folder = self.controller.current_project_data.get('projectFolderPath')
            if project_folder:
                for doc in docs_to_remove:
                    try:
                        file_path = Path(project_folder) / doc.get('path', '')
                        if file_path.exists() and file_path.is_file():
                            file_path.unlink()
                    except Exception as e:
                        QMessageBox.warning(self, "Deletion Warning", f"Could not delete physical file: {doc.get('name')}\n{e}")

        self.refresh_doc_tree()

    def update_controller_project_data_from_form(self):
        oem_details = self._get_section_data()
        if not oem_details:
            return
        
        for key, widget in self.entries.items():
            if isinstance(widget, QLineEdit):
                oem_details[key] = widget.text().strip()
            elif isinstance(widget, QDateEdit):
                oem_details[key] = widget.date().toString("yyyy-MM-dd")

# ========================================================================
# Class 6: NewProjectP4_ProposalOrder
# ========================================================================
class NewProjectP4_ProposalOrder(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='proposalOrderDetails')
        self.entries = {}
        self.doc_labels = {}

        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)

        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font()
        font.setPointSize(14)
        self.project_name_header_label.setFont(font)
        
        page_title_label = QLabel("PROPOSAL & ORDER DETAILS:")
        font = page_title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        page_title_label.setFont(font)
        
        content_layout.addWidget(self.project_name_header_label)
        content_layout.addWidget(page_title_label)
        content_layout.addSpacing(15)

        # --- Scroll Area Setup ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_content_widget)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- Section 1: Office Proposal ---
        s1_frame = QFrame()
        s1_frame.setObjectName("CardFrame")
        s1_frame.setFrameShape(QFrame.Shape.StyledPanel)
        s1_layout = QVBoxLayout(s1_frame)
        s1_layout.addWidget(QLabel("<b>Office Proposal</b>"))
        
        self.entries['officeProposalId'] = self._create_labeled_entry(s1_layout, "Office Proposal ID:")
        self.entries['proposalDate'] = self._create_date_entry(s1_layout, "Proposal Date:")
        self.doc_labels['proposalDocuments'] = self._create_document_row(
            s1_layout, 'proposalDocuments', 'proposalDocuments'
        )
        scroll_layout.addWidget(s1_frame)
        
        # --- Section 2: CEO Approval ---
        s2_frame = QFrame()
        s2_frame.setObjectName("CardFrame")
        s2_frame.setFrameShape(QFrame.Shape.StyledPanel)
        s2_layout = QVBoxLayout(s2_frame)
        s2_layout.addWidget(QLabel("<b>CEO Approval</b>"))
        self.doc_labels['ceoApprovalDocuments'] = self._create_document_row(s2_layout, 'ceoApprovalDocuments', 'ceoApprovalDocuments')
        scroll_layout.addWidget(s2_frame)
        
        # --- Section 3: Department Work Order ---
        s3_frame = QFrame()
        s3_frame.setObjectName("CardFrame")
        s3_frame.setFrameShape(QFrame.Shape.StyledPanel)
        s3_layout = QVBoxLayout(s3_frame)
        s3_layout.addWidget(QLabel("<b>Department Work Order</b>"))
        self.entries['departmentWorkOrderId'] = self._create_labeled_entry(s3_layout, "Dept. Work Order ID:")
        self.entries['issuingDate'] = self._create_date_entry(s3_layout, "Issuing Date:")
        self.doc_labels['workOrderDocuments'] = self._create_document_row(s3_layout, 'workOrderDocuments', 'workOrderDocuments')
        scroll_layout.addWidget(s3_frame)
        
        scroll_area.setWidget(scroll_content_widget)
        content_layout.addWidget(scroll_area)
        
        # --- Navigation ---
        self.main_layout.addLayout(
            self._create_navigation_buttons(
                back_page="NewProjectP3_OEM",
                next_page_or_action="NewProjectP4A_Scope"
            )
        )

    # --- CORRECTED HELPER METHODS ---
    def _create_labeled_entry(self, parent_layout, label_text):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(180)
        layout.addWidget(label)
        entry = QLineEdit()
        layout.addWidget(entry)
        parent_layout.addLayout(layout)
        return entry

    def _create_date_entry(self, parent_layout, label_text):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(180)
        layout.addWidget(label)
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(date_edit, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        parent_layout.addLayout(layout)
        return date_edit

    def _create_document_row(self, parent_layout, doc_key, subfolder_key):
        doc_layout = QHBoxLayout()
        doc_label_text = QLabel("Documents:")
        doc_label_text.setFixedWidth(180)
        doc_layout.addWidget(doc_label_text)
        display_label = QLabel("No file selected.")
        display_label.setStyleSheet("padding: 3px; border: 1px solid gray; border-radius: 3px;")
        browse_button = QPushButton("Browse")
        browse_button.setFixedWidth(80)
        target_subfolder = SUBFOLDER_NAMES.get(subfolder_key, "Misc_Documents")
        browse_button.clicked.connect(lambda: self._handle_document_selection(doc_key, display_label, target_subfolder, allow_multiple=False))
        doc_layout.addWidget(display_label, 1)
        doc_layout.addWidget(browse_button)
        parent_layout.addLayout(doc_layout)
        return display_label

    def on_show(self):
        super().on_show()
        details = self._get_section_data()
        
        for key, widget in self.entries.items():
            value = details.get(key, '')
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QDateEdit):
                if value:
                    widget.setDate(datetime.datetime.strptime(value, "%Y-%m-%d").date())
                else:
                    widget.setDate(datetime.date.today())
                    
        for doc_key, label_widget in self.doc_labels.items():
            docs_list = details.get(doc_key, [])
            label_widget.setText(docs_list[0].get('name', "No file selected.") if docs_list and isinstance(docs_list[0], dict) else "No file selected.")

    def update_controller_project_data_from_form(self):
        details = self._get_section_data()
        if not details:
            return
            
        for key, widget in self.entries.items():
            if isinstance(widget, QLineEdit):
                details[key] = widget.text().strip()
            elif isinstance(widget, QDateEdit):
                details[key] = widget.date().toString("yyyy-MM-dd")

# ========================================================================
# Class 7: NewProjectP4A_Scope
# ========================================================================
class NewProjectP4A_Scope(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='scopeOfWorkDetails')
        
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)

        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font()
        font.setPointSize(14)
        self.project_name_header_label.setFont(font)
        
        page_title_label = QLabel("SCOPE OF WORK DETAILS:")
        font = page_title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        page_title_label.setFont(font)

        content_layout.addWidget(self.project_name_header_label)
        content_layout.addWidget(page_title_label)
        content_layout.addSpacing(20)

        # --- Form Fields ---
        scope_layout = QHBoxLayout()
        scope_label = QLabel("Scope of Work:")
        scope_label.setFixedWidth(150)
        scope_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        scope_layout.addWidget(scope_label)
        
        self.scope_text = QTextEdit()
        self.scope_text.setMinimumHeight(100)
        scope_layout.addWidget(self.scope_text)
        content_layout.addLayout(scope_layout, 1)

        # Document Widgets
        doc_layout = QHBoxLayout()
        doc_label_widget = QLabel("Documents:")
        doc_label_widget.setFixedWidth(150)
        doc_layout.addWidget(doc_label_widget)
        
        self.doc_path_label = QLabel("No file selected.")
        self.doc_path_label.setStyleSheet("padding: 3px; border: 1px solid gray; border-radius: 3px;")
        browse_button = QPushButton("Browse")
        browse_button.setFixedWidth(80)
        target_subfolder = SUBFOLDER_NAMES.get("scopeOfWorkDetails", "Misc_Documents")
        browse_button.clicked.connect(lambda: self._handle_document_selection('documents', self.doc_path_label, target_subfolder, allow_multiple=False))
        
        doc_layout.addWidget(self.doc_path_label, 1)
        doc_layout.addWidget(browse_button)
        content_layout.addLayout(doc_layout)

        # --- Navigation ---
        self.main_layout.addLayout(
            self._create_navigation_buttons(
                back_page="NewProjectP4_ProposalOrder",
                next_page_or_action="NewProjectP4B_BOM"
            )
        )
    
    def on_show(self):
        super().on_show()
        details = self._get_section_data()
        self.scope_text.setPlainText(details.get('scope', ''))
        docs = details.get('documents', [])
        self.doc_path_label.setText(docs[0].get('name', "No file selected.") if docs else "No file selected.")

    def update_controller_project_data_from_form(self):
        details = self._get_section_data()
        if details:
            details['scope'] = self.scope_text.toPlainText().strip()
# ========================================================================
# Class 8: NewProjectP4B_BOM
# ========================================================================
class NewProjectP4B_BOM(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='billOfMaterials')
        self.item_entries = {}

        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(10, 10, 10, 0)
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font()
        font.setPointSize(14)
        self.project_name_header_label.setFont(font)

        page_title_label = QLabel("BILL OF MATERIALS DETAILS:")
        font = page_title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        page_title_label.setFont(font)
        header_layout.addWidget(self.project_name_header_label)
        header_layout.addWidget(page_title_label)
        content_layout.addLayout(header_layout)

        # --- Entry Form ---
        entry_form_frame = QFrame()
        entry_form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        entry_form_layout = QVBoxLayout(entry_form_frame)
        entry_form_layout.addWidget(QLabel("<b>Add Item</b>"))

        item_fields_row1 = [("HSN:", "hsn"), ("Item:", "item"), ("Specs:", "specs")]
        item_fields_row2 = [("Qty:", "qty"), ("Unit Price:", "unitPrice"), ("GST%:", "gstPercent")]
        
        row1_layout = QHBoxLayout()
        for label_text, key in item_fields_row1:
            row1_layout.addWidget(QLabel(label_text))
            entry = QLineEdit()
            self.item_entries[key] = entry
            row1_layout.addWidget(entry)
        entry_form_layout.addLayout(row1_layout)

        row2_layout = QHBoxLayout()
        for label_text, key in item_fields_row2:
            row2_layout.addWidget(QLabel(label_text))
            entry = QLineEdit()
            self.item_entries[key] = entry
            row2_layout.addWidget(entry)
        entry_form_layout.addLayout(row2_layout)
        
        add_item_button = QPushButton("Add Item to BoM")
        add_item_button.clicked.connect(self.add_item_to_bom)
        entry_form_layout.addWidget(add_item_button, 0, Qt.AlignmentFlag.AlignRight)
        
        content_layout.addWidget(entry_form_frame)
        
        # --- BoM Table ---
        self.bom_tree = QTreeWidget()
        bom_columns = {"sl_no": "SL.", "hsn": "HSN", "item": "Item", "specs": "Specs", "qty": "Qty", "unitPrice": "Unit Price", "amount": "Amount", "gstPercent": "GST%", "gstAmount": "GST Amt.", "total": "Total"}
        self.bom_tree.setHeaderLabels(list(bom_columns.values()))
        col_widths = {"sl_no": 30, "hsn": 70, "item": 200, "specs": 250, "qty":60, "unitPrice":90, "amount":90, "gstPercent":60, "gstAmount":90, "total":100}
        for i, key in enumerate(bom_columns.keys()):
            self.bom_tree.setColumnWidth(i, col_widths.get(key, 70))
        
        content_layout.addWidget(self.bom_tree, 1)

        # --- Table Buttons & Summary ---
        remove_item_button = QPushButton("Remove Selected Item")
        remove_item_button.clicked.connect(self.remove_selected_item)
        
        self.total_bom_amount_label = QLabel("Total BoM Amount (INR): 0.00")
        self.amount_in_words_label = QLabel("Amount in Words: Zero")
        font = self.amount_in_words_label.font()
        font.setItalic(True)
        self.amount_in_words_label.setFont(font)
        
        summary_layout = QHBoxLayout()
        summary_layout.addWidget(remove_item_button)
        summary_layout.addStretch(1)
        
        summary_text_layout = QVBoxLayout()
        summary_text_layout.addWidget(self.total_bom_amount_label, 0, Qt.AlignmentFlag.AlignRight)
        summary_text_layout.addWidget(self.amount_in_words_label, 0, Qt.AlignmentFlag.AlignRight)
        summary_layout.addLayout(summary_text_layout)

        content_layout.addLayout(summary_layout)
        
        # --- Navigation ---
        self.main_layout.addLayout(
            self._create_navigation_buttons(
                back_page="NewProjectP4A_Scope",
                next_page_or_action="NewProjectP5_OEN"
            )
        )

    def on_show(self):
        super().on_show()
        self._get_section_data() 
        self.refresh_bom_table()
        self.update_summary_fields()

    def add_item_to_bom(self):
        bom_data = self._get_section_data()
        if bom_data is None: return
        try:
            new_item = {key: entry.text().strip() for key, entry in self.item_entries.items()}
            if not new_item.get('item'):
                QMessageBox.warning(self, "Missing Info", "Item name is required.")
                return
            
            qty = float(new_item.get('qty') or 0.0)
            unit_price = float(new_item.get('unitPrice') or 0.0)
            gst_percent = float(new_item.get('gstPercent') or 0.0)

            new_item.update({
                'qty': qty, 'unitPrice': unit_price, 'gstPercent': gst_percent,
                'amount': qty * unit_price,
                'gstAmount': (qty * unit_price) * (gst_percent / 100.0),
                'total': (qty * unit_price) * (1 + gst_percent / 100.0),
                'sl_no': len(bom_data.get('items', [])) + 1,
                'fulfillments': []
            })
            
            bom_data.setdefault('items', []).append(new_item)
            self.refresh_bom_table()
            for entry_widget in self.item_entries.values(): entry_widget.clear()
            self.item_entries['hsn'].setFocus()
        except ValueError:
            QMessageBox.critical(self, "Input Error", "Please enter valid numbers for Qty, Unit Price, and GST%.")

    def remove_selected_item(self):
        selected_items = self.bom_tree.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select an item to remove.")
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to remove the selected item(s)?")
        if reply == QMessageBox.StandardButton.No:
            return
        
        bom_data = self._get_section_data()
        sl_nos_to_remove = {int(item.text(0)) for item in selected_items}
        bom_data['items'] = [item for item in bom_data['items'] if item.get('sl_no') not in sl_nos_to_remove]
        for i, item in enumerate(bom_data['items']):
            item['sl_no'] = i + 1
        
        self.refresh_bom_table()

    def refresh_bom_table(self):
        self.bom_tree.clear()
        bom_data = self._get_section_data()
        if bom_data and 'items' in bom_data:
            for item in bom_data['items']:
                values = [
                    str(item.get('sl_no', '')), item.get('hsn', ''), item.get('item', ''),
                    item.get('specs', ''), f"{item.get('qty', 0.0):.2f}", f"{item.get('unitPrice', 0.0):.2f}",
                    f"{item.get('amount', 0.0):.2f}", f"{item.get('gstPercent', 0.0):.2f}%",
                    f"{item.get('gstAmount', 0.0):.2f}", f"{item.get('total', 0.0):.2f}"
                ]
                tree_item = QTreeWidgetItem(values)
                self.bom_tree.addTopLevelItem(tree_item)
        self.update_summary_fields()

    def update_summary_fields(self):
        bom_data = self._get_section_data()
        total_sum = sum(item.get('total', 0.0) for item in bom_data.get('items', [])) if bom_data else 0.0
        self.total_bom_amount_label.setText(f"Total BoM Amount (INR): {total_sum:,.2f}")
        
        # CORRECTED: Call the function from the 'utils' module
        amount_words = utils.convert_number_to_words(total_sum)
        
        self.amount_in_words_label.setText(f"Amount in Words: {amount_words}")
        if bom_data:
            bom_data['amountInWords'] = amount_words
        
    def handle_next(self, target_page):
        self.update_summary_fields()
        super().handle_next(target_page)

# ========================================================================
# Class 9: NewProjectP5_OEN
# ========================================================================
class NewProjectP5_OEN(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='oenDetails')
        self.entries = {}
        self.doc_labels = {}

        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)

        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font()
        font.setPointSize(14)
        self.project_name_header_label.setFont(font)

        page_title_label = QLabel("OEN DETAILS:")
        font = page_title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        page_title_label.setFont(font)

        content_layout.addWidget(self.project_name_header_label)
        content_layout.addWidget(page_title_label)
        content_layout.addSpacing(10)

        # --- Scroll Area ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        scroll_content_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_content_widget)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- OEN Section ---
        oen_frame = QFrame()
        oen_layout = QVBoxLayout(oen_frame)
        oen_layout.setContentsMargins(0,0,0,0)
        oen_layout.addWidget(QLabel("<b>OEN Section</b>"))

        self.entries['oenRegistrationNo'] = self._create_labeled_entry(oen_layout, "OEN Registration No:")
        self.entries['registrationDate'] = self._create_date_entry(oen_layout, "OEN Registration Date:")
        self.entries['officeOenNo'] = self._create_labeled_entry(oen_layout, "Office OEN No:")
        self.entries['oenDate'] = self._create_date_entry(oen_layout, "Office OEN Date:")
        self.doc_labels['documents'] = self._create_document_row(oen_layout, 'documents', 'oenDetails')
        scroll_layout.addWidget(oen_frame)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        scroll_layout.addWidget(separator)

        # --- Work Order Section ---
        work_order_frame = QFrame()
        work_order_layout = QVBoxLayout(work_order_frame)
        work_order_layout.setContentsMargins(0,0,0,0)
        work_order_layout.addWidget(QLabel("<b>Work Order Section</b>"))

        self.entries['officeWorkOrderId'] = self._create_labeled_entry(work_order_layout, "Office Work Order ID:")
        self.entries['officeWorkOrderDate'] = self._create_date_entry(work_order_layout, "Work Order Date:")
        self.doc_labels['officeWorkOrderDocuments'] = self._create_document_row(work_order_layout, 'officeWorkOrderDocuments', 'officeWorkOrderDocuments')
        scroll_layout.addWidget(work_order_frame)
        
        scroll_area.setWidget(scroll_content_widget)
        content_layout.addWidget(scroll_area, 1)

        # --- Navigation ---
        self.main_layout.addLayout(
            self._create_navigation_buttons(
                back_page="NewProjectP4B_BOM",
                next_page_or_action=None,
                finish_action_details={
                    "text": "FINISH PROJECT CREATION",
                    "command": self.handle_finish_project
                }
            )
        )

    def _create_labeled_entry(self, parent_layout, label_text):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(180)
        layout.addWidget(label)
        entry = QLineEdit()
        layout.addWidget(entry)
        parent_layout.addLayout(layout)
        return entry

    def _create_date_entry(self, parent_layout, label_text):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(180)
        layout.addWidget(label)
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(date_edit, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        parent_layout.addLayout(layout)
        return date_edit

    def _create_document_row(self, parent_layout, doc_key, subfolder_key):
        doc_layout = QHBoxLayout()
        doc_label_text = QLabel("Documents:")
        doc_label_text.setFixedWidth(180)
        doc_layout.addWidget(doc_label_text)
        display_label = QLabel("No file selected.")
        display_label.setStyleSheet("padding: 3px; border: 1px solid gray; border-radius: 3px;")
        browse_button = QPushButton("Browse")
        browse_button.setFixedWidth(80)
        target_subfolder = SUBFOLDER_NAMES.get(subfolder_key, "Misc_Documents")
        browse_button.clicked.connect(lambda: self._handle_document_selection(doc_key, display_label, target_subfolder, allow_multiple=False))
        doc_layout.addWidget(display_label, 1)
        doc_layout.addWidget(browse_button)
        parent_layout.addLayout(doc_layout)
        return display_label

    def on_show(self):
        super().on_show()
        details = self._get_section_data()
        
        for key, widget in self.entries.items():
            value = details.get(key, '')
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QDateEdit):
                if value:
                    widget.setDate(datetime.datetime.strptime(value, "%Y-%m-%d").date())
                else:
                    widget.setDate(datetime.date.today())
                    
        for doc_key, label_widget in self.doc_labels.items():
             docs = details.get(doc_key, [])
             label_widget.setText(docs[0].get('name', "No file selected.") if docs else "No file selected.")

    def update_controller_project_data_from_form(self):
        details = self._get_section_data()
        if not details:
            return
            
        for key, widget in self.entries.items():
            if isinstance(widget, QLineEdit):
                details[key] = widget.text().strip()
            elif isinstance(widget, QDateEdit):
                details[key] = widget.date().toString("yyyy-MM-dd")

    def handle_finish_project(self):
        self.update_controller_project_data_from_form()
        if self.controller.save_project_to_sqlite(self.controller.current_project_data, is_final_step=True):
            QMessageBox.information(self, "Project Created", "The new project has been successfully created and saved.")
            self.navigate_request.emit("HomeView")

# ========================================================================
# Class 10: DocumentLinksDialog (Helper for Details View)
# ========================================================================
class DocumentLinksDialog(QDialog):
    def __init__(self, parent, docs_list, project_folder_path):
        super().__init__(parent)
        self.setWindowTitle("Document Links")
        self.setMinimumSize(400, 300)
        self.project_folder_path = project_folder_path
        layout = QVBoxLayout(self)

        # Use our new custom widget
        self.text_box = LinkInterceptingBrowser(self)

        layout.addWidget(self.text_box)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.populate_links(docs_list)

    def populate_links(self, docs_list):
        if not docs_list:
            self.text_box.setHtml("No documents found for this event.")
            return
        html = ""
        for doc in docs_list:
            if not isinstance(doc, dict): continue
            doc_name = doc.get('name', 'N/A'); path_str = doc.get('path', ''); full_path = None
            if doc.get('type') == 'project_file' and self.project_folder_path:
                full_path = Path(self.project_folder_path) / path_str
            elif doc.get('type', '').startswith('local_file_link'):
                full_path = Path(path_str)
            if full_path and full_path.exists():
                html += f'<a href="{full_path.as_uri()}">{doc_name}</a><br>'
            else:
                html += f'{doc_name} (File Missing)<br>'
        self.text_box.setHtml(html)


# ========================================================================
# Class 11: ProjectDetailsView
# ========================================================================

class ProjectDetailsView(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key=None)
        
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Top Info Frame ---
        top_info_frame = QWidget()
        top_info_layout = QVBoxLayout(top_info_frame)
        top_info_layout.setContentsMargins(0,0,0,0)
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font(); font.setPointSize(16); font.setBold(True)
        self.project_name_header_label.setFont(font)
        self.dept_lead_label = QLabel("<DEPT. NAME | PROJECT LEAD>")
        font = self.dept_lead_label.font(); font.setPointSize(12)
        self.dept_lead_label.setFont(font)
        self.status_label = QLabel("STATUS: <CONDITIONAL>")
        font = self.status_label.font(); font.setPointSize(12); font.setBold(True)
        self.status_label.setFont(font)
        top_info_layout.addWidget(self.project_name_header_label)
        top_info_layout.addWidget(self.dept_lead_label)
        top_info_layout.addWidget(self.status_label)
        self.main_layout.addWidget(top_info_frame)

        # --- Tab Widget ---
        tab_widget = QTabWidget()
        
        # Tab 1: BOM Fulfillment
        bom_tab = QWidget()
        bom_tab_layout = QVBoxLayout(bom_tab)
        self.details_tree = QTreeWidget()
        self.details_tree.setHeaderLabels(["Item / Fulfillment Date", "Details / Fulfilled Qty"])
        self.details_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.details_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.details_tree.itemChanged.connect(self._bom_item_edited)
        bom_tab_layout.addWidget(self.details_tree)
        
        bom_buttons = QHBoxLayout()
        bom_buttons.addStretch()
        delete_fulfillment_button = QPushButton("Delete Selected Fulfillment Entry")
        delete_fulfillment_button.clicked.connect(self._delete_bom_fulfillment_entry)
        bom_buttons.addWidget(delete_fulfillment_button)
        bom_tab_layout.addLayout(bom_buttons)
        tab_widget.addTab(bom_tab, "BOM Fulfillment")
        
        # Tab 2: Fulfillment Events
        events_tab = QWidget()
        events_tab_layout = QVBoxLayout(events_tab)
        self.event_tree = QTreeWidget()
        self.event_tree.setHeaderLabels(["Date", "Details"])
        self.event_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.event_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.event_tree.itemDoubleClicked.connect(self.handle_event_tree_click)
        events_tab_layout.addWidget(self.event_tree)
        
        event_buttons = QHBoxLayout()
        event_buttons.addStretch()
        edit_event_button = QPushButton("Edit Event")
        edit_event_button.clicked.connect(self._edit_selected_event)
        delete_event_button = QPushButton("Delete Event")
        delete_event_button.clicked.connect(self._delete_selected_event)
        event_buttons.addWidget(edit_event_button)
        event_buttons.addWidget(delete_event_button)
        events_tab_layout.addLayout(event_buttons)
        tab_widget.addTab(events_tab, "Fulfillment Events")

        self.main_layout.addWidget(tab_widget, 1)

        # --- Bottom Navigation ---
        bottom_bar_layout = QHBoxLayout()
        back_button = QPushButton("<< BACK TO HOME"); back_button.clicked.connect(lambda: self.navigate_request.emit("HomeView"))
        bottom_bar_layout.addWidget(back_button)
        bottom_bar_layout.addStretch(1)
        financials_button = QPushButton("FINANCIAL DETAILS"); financials_button.clicked.connect(lambda: self.navigate_request.emit("FinancialDetailsView"))
        process_fulfillment_button = QPushButton("PROCESS FULFILLMENT"); process_fulfillment_button.clicked.connect(lambda: self.navigate_request.emit("FulfillmentView"))
        exit_button = QPushButton("EXIT"); exit_button.setObjectName("ExitButton"); exit_button.clicked.connect(self.handle_exit)
        bottom_bar_layout.addWidget(financials_button); bottom_bar_layout.addWidget(process_fulfillment_button); bottom_bar_layout.addWidget(exit_button)
        self.main_layout.addLayout(bottom_bar_layout)

    def on_show(self):
        super().on_show()
        project = self.controller.current_project_data
        if not project: 
            self.navigate_request.emit("HomeView")
            return
        
        self.controller.update_project_status(project)

        self.project_name_header_label.setText(project.get('projectName', '<PROJECT NAME>'))
        department_name = project.get('departmentDetails', {}).get('name', 'N/A')
        self.dept_lead_label.setText(f"Dept: {department_name} | Lead: {project.get('projectLead', 'N/A')}")
        self.status_label.setText(f"STATUS: {project.get('status', 'N/A').upper()}")
        
        self.populate_bom_table(project)
        self.populate_fulfillment_tree(project)

    def _save_and_refresh(self):
        project = self.controller.current_project_data
        self.controller.update_project_status(project)
        self.controller.save_project_to_sqlite(project)
        self.on_show()

    def populate_bom_table(self, project):
        self.details_tree.blockSignals(True)
        self.details_tree.clear()
        bom_items = project.get('billOfMaterials', {}).get('items', [])
        
        if not bom_items:
            self.details_tree.addTopLevelItem(QTreeWidgetItem(["No items in Bill of Materials."]))
            self.details_tree.blockSignals(False)
            return

        for bom_item_data in bom_items:
            summary = self._get_bom_item_summary(bom_item_data)
            item_text = f"SL.{bom_item_data.get('sl_no', '')}: {bom_item_data.get('item', 'N/A')}"
            summary_text = (
                f"Total Required: {summary['original_qty']:.2f} | "
                f"Fulfilled: {summary['fulfilled_qty']:.2f} | "
                f"Pending: {summary['pending_qty']:.2f}"
            )
            
            parent_item = QTreeWidgetItem([item_text, summary_text])
            parent_item.setFlags(parent_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            font = parent_item.font(0); font.setBold(True); parent_item.setFont(0, font)
            self.details_tree.addTopLevelItem(parent_item)
            
            for fulfillment_entry in bom_item_data.get('fulfillments', []):
                child_item = QTreeWidgetItem(parent_item, [
                    f"  - {fulfillment_entry.get('fulfilledDate', 'N/A')}",
                    str(fulfillment_entry.get('fulfilledQty', 0.0))
                ])
                child_item.setData(0, Qt.ItemDataRole.UserRole, {'bom_item_sl': bom_item_data.get('sl_no'), 'fulfillment_entry': fulfillment_entry})
                child_item.setFlags(child_item.flags() | Qt.ItemFlag.ItemIsEditable)
                parent_item.addChild(child_item)
        
        self.details_tree.expandAll()
        self.details_tree.blockSignals(False)

    def _delete_bom_fulfillment_entry(self):
        selected = self.details_tree.currentItem()
        if not selected or not selected.data(0, Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, "Selection Error", "Please select a specific fulfillment entry (a child item) to delete.")
            return

        data = selected.data(0, Qt.ItemDataRole.UserRole)
        bom_item_sl = data['bom_item_sl']
        fulfillment_to_remove = data['fulfillment_entry']
        
        reply = QMessageBox.question(self, "Confirm Deletion", 
            f"Are you sure you want to delete the fulfillment of {fulfillment_to_remove['fulfilledQty']} units from {fulfillment_to_remove['fulfilledDate']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            bom_item = next((item for item in self.controller.current_project_data['billOfMaterials']['items'] if item.get('sl_no') == bom_item_sl), None)
            if not bom_item:
                QMessageBox.critical(self, "Error", "Could not find parent BOM item.")
                return

            target_id = fulfillment_to_remove.get('fulfillmentId')
            initial_len = len(bom_item['fulfillments'])

            if target_id:
                bom_item['fulfillments'] = [f for f in bom_item['fulfillments'] if f.get('fulfillmentId') != target_id]
            else: # Fallback for old data
                bom_item['fulfillments'].remove(fulfillment_to_remove)

            if len(bom_item['fulfillments']) < initial_len:
                self._save_and_refresh()
            else:
                QMessageBox.critical(self, "Deletion Failed", "Could not find the entry to delete.")

    def _bom_item_edited(self, item, column):
        if column != 1: return
        
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data: return

        try:
            new_qty = float(item.text(1))
            if new_qty < 0: raise ValueError
            data['fulfillment_entry']['fulfilledQty'] = new_qty
            self._save_and_refresh()
        except (ValueError, TypeError):
            QMessageBox.critical(self, "Invalid Input", "Please enter a valid, non-negative number for the quantity.")
            self.details_tree.blockSignals(True)
            item.setText(1, str(data['fulfillment_entry']['fulfilledQty']))
            self.details_tree.blockSignals(False)

    def populate_fulfillment_tree(self, project):
        # This method remains largely the same as the previous correct version
        self.event_tree.clear()
        doc_types = {
            'officeTaxInvoice': 'Office Tax Invoice', 'deliveryChallan': 'Delivery Challan',
            'installationCertificate': 'Installation Certificate', 'workCompletionCertificate': 'Work Completion Certificate'
        }
        all_events = []
        for key, label in doc_types.items():
            for doc_record in project.get('fulfillmentDocs', {}).get(key, []):
                event_data_copy = doc_record.copy()
                event_data_copy['event_type_key'] = key
                event_data_copy['event_type_label'] = label
                event_data_copy['original_ref'] = doc_record 
                all_events.append(event_data_copy)

        sorted_events = sorted(all_events, key=lambda x: x.get('date', '9999-12-31'), reverse=True)
        
        for event_data in sorted_events:
            date = event_data.get('date', 'N/A')
            label = event_data.get('event_type_label', 'Event')
            details = f"{label} (Ref: {event_data.get('refNo', 'N/A')})"
            item = QTreeWidgetItem([date, details])
            item.setData(0, Qt.ItemDataRole.UserRole, event_data)
            self.event_tree.addTopLevelItem(item)

    def _edit_selected_event(self):
        # This method remains largely the same as the previous correct version
        selected = self.event_tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Selection Error", "Please select an event to edit.")
            return

        event_data = selected.data(0, Qt.ItemDataRole.UserRole)
        dialog = EditFulfillmentEventDialog(event_data.copy(), self.controller.current_project_data.get('projectFolderPath'), self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_data = dialog.get_updated_data()
            original_event_ref = event_data['original_ref']
            original_event_ref.clear()
            original_event_ref.update(updated_data)
            self._save_and_refresh()
    
    def _delete_selected_event(self):
        # This method remains largely the same as the previous correct version
        selected = self.event_tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Selection Error", "Please select an event to delete.")
            return
            
        event_data = selected.data(0, Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(self, "Confirm Deletion", 
            f"Are you sure you want to delete this event?\n'{event_data.get('event_type_label')} - Ref: {event_data.get('refNo', 'N/A')}'",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if reply == QMessageBox.StandardButton.Yes:
            event_key = event_data['event_type_key']
            original_event_ref = event_data['original_ref']
            try:
                self.controller.current_project_data['fulfillmentDocs'][event_key].remove(original_event_ref)
                self._save_and_refresh()
            except (KeyError, ValueError):
                 QMessageBox.critical(self, "Error", "Could not find the event to delete.")

    def _get_bom_item_summary(self, item_dict):
        if not isinstance(item_dict, dict): return {}
        fulfillments = item_dict.get('fulfillments', [])
        total_fulfilled_qty = sum(float(f.get('fulfilledQty', 0.0)) for f in fulfillments)
        original_qty = float(item_dict.get('qty', 0.0))
        pending_qty = max(0.0, original_qty - total_fulfilled_qty)
        return {'original_qty': original_qty, 'fulfilled_qty': total_fulfilled_qty, 'pending_qty': pending_qty}

    def handle_event_tree_click(self, item, column):
        # This method remains largely the same as the previous correct version
        event_data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(event_data, dict) and event_data.get('documents'):
            doc_data = event_data['documents'][0]
            project_folder = self.controller.current_project_data.get('projectFolderPath')
            full_path = Path(project_folder) / doc_data.get('path', '') if project_folder and doc_data.get('path') else None
            if full_path and full_path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))
            else:
                QMessageBox.warning(self, "File Not Found", f"Could not find the file:\n{doc_data.get('path', 'N/A')}")


# ========================================================================
# Class 12: FinancialDetailsView
# ========================================================================

# In ui/pages.py, replace the FinancialDetailsView class

class FinancialDetailsView(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='financialDetails')
        
        self.temp_transaction_docs = []
        self._trans_data_cache = {}

        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        content_layout.setContentsMargins(10, 10, 10, 10)

        # --- Top Info ---
        top_info_layout = QVBoxLayout()
        self.project_name_header_label = QLabel("<PROJECT NAME>"); font = self.project_name_header_label.font(); font.setPointSize(16); font.setBold(True); self.project_name_header_label.setFont(font)
        self.dept_lead_label = QLabel("<DEPT. NAME | PROJECT LEAD>"); font = self.dept_lead_label.font(); font.setPointSize(12); self.dept_lead_label.setFont(font)
        page_title_label = QLabel("FINANCIAL DETAILS"); font = page_title_label.font(); font.setPointSize(18); font.setBold(True); page_title_label.setFont(font)
        top_info_layout.addWidget(self.project_name_header_label); top_info_layout.addWidget(self.dept_lead_label); top_info_layout.addWidget(page_title_label)
        content_layout.addLayout(top_info_layout)

        # --- Main Splitter Layout ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(main_splitter, 1)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Payment Form
        payment_form = QFrame(); payment_form.setFrameShape(QFrame.Shape.StyledPanel)
        payment_form_layout = QVBoxLayout(payment_form)
        payment_form_layout.addWidget(QLabel("<b>Enter Client Payment Details</b>"))

        self.transaction_entries = {}
        form_fields = [("Transaction Details:", "transactionDetails"), ("Amount Received (INR):", "amountReceived")]
        for label_text, key in form_fields:
            layout = QHBoxLayout(); label = QLabel(label_text); label.setFixedWidth(150); layout.addWidget(label)
            entry = QLineEdit(); self.transaction_entries[key] = entry; layout.addWidget(entry)
            payment_form_layout.addLayout(layout)

        date_layout = QHBoxLayout(); date_label = QLabel("Transaction Date:"); date_label.setFixedWidth(150); date_layout.addWidget(date_label)
        self.transaction_entries['date'] = QDateEdit(calendarPopup=True); self.transaction_entries['date'].setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self.transaction_entries['date'], 0, Qt.AlignmentFlag.AlignLeft); date_layout.addStretch(1)
        payment_form_layout.addLayout(date_layout)

        # Document Uploader for New Transactions
        doc_layout = QHBoxLayout(); doc_label = QLabel("Documents:"); doc_label.setFixedWidth(150); doc_layout.addWidget(doc_label)
        self.doc_display_label = QLabel("No file(s) staged."); self.doc_display_label.setStyleSheet("padding: 3px; border: 1px solid gray; border-radius: 3px;")
        add_doc_button = QPushButton("Add Document(s)"); add_doc_button.clicked.connect(self._add_transaction_documents)
        doc_layout.addWidget(self.doc_display_label, 1); doc_layout.addWidget(add_doc_button)
        payment_form_layout.addLayout(doc_layout)

        add_trans_button = QPushButton("Add Transaction"); add_trans_button.clicked.connect(self.add_transaction)
        payment_form_layout.addWidget(add_trans_button, 0, Qt.AlignmentFlag.AlignRight)
        left_layout.addWidget(payment_form)

        # Transaction History
        history_frame = QFrame(); history_frame.setFrameShape(QFrame.Shape.StyledPanel)
        history_layout = QVBoxLayout(history_frame)
        history_layout.addWidget(QLabel("<b>Client Transaction History</b>"))
        self.trans_tree = QTreeWidget(); self.trans_tree.setHeaderLabels(["SL.", "Details", "Date", "Received", "Pending"])
        self.trans_tree.itemSelectionChanged.connect(self._on_transaction_selected)
        history_layout.addWidget(self.trans_tree)
        left_layout.addWidget(history_frame, 1)
        
        main_splitter.addWidget(left_panel)

        # --- Right Panel (Document Viewer) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.doc_viewer_label = QLabel("Documents for Selected Transaction")
        self.doc_viewer_tree = QTreeWidget(); self.doc_viewer_tree.setHeaderHidden(True)
        self.doc_viewer_tree.itemDoubleClicked.connect(self._open_document_link)
        right_layout.addWidget(self.doc_viewer_label); right_layout.addWidget(self.doc_viewer_tree, 1)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([700, 300])
        
        # --- Summary & Navigation ---
        summary_layout = QVBoxLayout(); summary_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.total_pending_label = QLabel("TOTAL PENDING IN WORDS: <CALCULATING>"); self.total_vendor_payment_label = QLabel("TOTAL VENDOR PAYMENTS: 0.00")
        self.profit_label = QLabel("PROJECT PROFIT: 0.00")
        summary_layout.addWidget(self.total_pending_label); summary_layout.addWidget(self.total_vendor_payment_label); summary_layout.addWidget(self.profit_label)
        content_layout.addLayout(summary_layout)

        bottom_bar_layout = QHBoxLayout()
        back_button = QPushButton("<< BACK TO PROJECT DETAILS"); back_button.clicked.connect(lambda: self.navigate_request.emit("ProjectDetailsView"))
        vendor_button = QPushButton("VENDORS PAYMENT"); vendor_button.setObjectName("VendorButton"); vendor_button.clicked.connect(lambda: self.navigate_request.emit("VendorPaymentView"))
        bottom_bar_layout.addWidget(back_button); bottom_bar_layout.addWidget(vendor_button); bottom_bar_layout.addStretch(1)
        save_button = QPushButton("SAVE FINANCIALS"); save_button.setObjectName("FinishButton"); save_button.clicked.connect(self.save_financial_details)
        bottom_bar_layout.addWidget(save_button)
        content_layout.addLayout(bottom_bar_layout)
        
    def on_show(self):
        super().on_show()
        project = self.controller.current_project_data
        if not project: self.navigate_request.emit("HomeView"); return
        
        self._get_section_data()
        self.transaction_entries['date'].setDate(QDate.currentDate())
        self.temp_transaction_docs.clear()
        self.doc_display_label.setText("No file(s) staged.")
        
        self.project_name_header_label.setText(project.get('projectName', '<PROJECT NAME>')); department_name = project.get('departmentDetails', {}).get('name', 'N/A')
        self.dept_lead_label.setText(f"Dept: {department_name} | Lead: {project.get('projectLead', 'N/A')}")
        
        self.recalculate_pending_amounts(); self.refresh_transaction_table(); self.update_financial_summary()
        self._on_transaction_selected()

    def _add_transaction_documents(self):
        target_subfolder = SUBFOLDER_NAMES.get("financialDetails", "Financial_Docs")
        # This helper method is in base_frame.py
        self._handle_document_selection('documents', self.doc_display_label, target_subfolder, allow_multiple=True, target_list=self.temp_transaction_docs)
    
    def add_transaction(self):
        fin_data = self._get_section_data()
        if fin_data is None: return
        details = self.transaction_entries['transactionDetails'].text().strip(); amount_str = self.transaction_entries['amountReceived'].text().strip()
        if not details or not amount_str: QMessageBox.warning(self, "Input Error", "Valid details and amount are required."); return
        try: amount = float(amount_str)
        except ValueError: QMessageBox.critical(self, "Input Error", "Please enter a valid number for amount."); return
        
        fin_data.setdefault('transactions', []).append({
            'transactionDetails': details, 'amountReceived': amount, 'date': self.transaction_entries['date'].date().toString("yyyy-MM-dd"), 
            'documents': list(self.temp_transaction_docs), 'sl_no': len(fin_data.get('transactions', [])) + 1
        })
        self.on_show()
        self.transaction_entries['transactionDetails'].clear(); self.transaction_entries['amountReceived'].clear()

    def refresh_transaction_table(self):
        self.trans_tree.clear()
        self._trans_data_cache.clear()
        fin_data = self._get_section_data()
        if fin_data and 'transactions' in fin_data:
            for trans in fin_data['transactions']:
                date_str = trans.get('date'); display_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y") if date_str else "N/A"
                values = [str(trans.get('sl_no','')), trans.get('transactionDetails',''), display_date, f"{trans.get('amountReceived',0.0):.2f}", f"{trans.get('amountPending',0.0):.2f}"]
                item = QTreeWidgetItem(values); self.trans_tree.addTopLevelItem(item); self._trans_data_cache[id(item)] = trans

    def _on_transaction_selected(self):
        self.doc_viewer_tree.clear()
        selected_items = self.trans_tree.selectedItems()
        if not selected_items: return
        
        trans_data = self._trans_data_cache.get(id(selected_items[0]))
        if not trans_data: return

        for doc in trans_data.get('documents', []):
            item = QTreeWidgetItem([doc['name']]); item.setData(0, Qt.ItemDataRole.UserRole, doc)
            item.setForeground(0, QBrush(QColor("#0969DA"))); item.setToolTip(0, "Double-click to open file")
            self.doc_viewer_tree.addTopLevelItem(item)
    
    def _open_document_link(self, item, column):
        doc_data = item.data(0, Qt.ItemDataRole.UserRole)
        project_folder = self.controller.current_project_data.get('projectFolderPath')
        if doc_data and project_folder and doc_data.get('path'):
            full_path = Path(project_folder) / doc_data['path']
            if full_path.exists(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))
            else: QMessageBox.warning(self, "File Not Found", f"Could not find file: {full_path}")

    # --- Other methods (recalculate_pending_amounts, update_financial_summary, save_financial_details) are unchanged ---
    def recalculate_pending_amounts(self):
        fin_data = self._get_section_data(); bom_total = self.controller.get_project_bom_total()
        if not fin_data: return
        sorted_trans = sorted(fin_data.get('transactions',[]), key=lambda x: (x.get('date', '9999-12-31'), x.get('sl_no', 0)))
        cumulative_received = 0.0
        for trans in sorted_trans: cumulative_received += float(trans.get('amountReceived', 0.0)); trans['amountPending'] = max(0.0, bom_total - cumulative_received)
        fin_data['transactions'] = sorted_trans

    def update_financial_summary(self):
        fin_data = self._get_section_data()
        if not fin_data: return
        total_received = sum(t.get('amountReceived', 0.0) for t in fin_data.get('transactions', [])); bom_total = self.controller.get_project_bom_total()
        total_pending = max(0.0, bom_total - total_received); fin_data['totalAmountReceived'] = total_received; fin_data['totalAmountPending'] = total_pending
        fin_data['totalPendingInWords'] = utils.convert_number_to_words(total_pending); self.total_pending_label.setText(f"TOTAL PENDING IN WORDS: {fin_data['totalPendingInWords'].upper()}")
        total_vendor_payments = sum(p.get('totalAmount', 0.0) for p in self.controller.current_project_data.get('vendorPayments', [])); profit = total_received - total_vendor_payments
        self.total_vendor_payment_label.setText(f"TOTAL VENDOR PAYMENTS: {total_vendor_payments:,.2f}"); self.profit_label.setText(f"PROJECT PROFIT: {profit:,.2f}")
        self.profit_label.setStyleSheet("color: green;" if profit >= 0 else "color: red;"); fin_data.update({'totalVendorPayments': total_vendor_payments, 'projectProfit': profit})

    def save_financial_details(self):
        self.recalculate_pending_amounts(); self.update_financial_summary()
        if self.controller.save_project_to_sqlite(self.controller.current_project_data): QMessageBox.information(self, "Saved", "Financial details have been saved successfully.")
        else: QMessageBox.critical(self, "Save Error", "Could not save financial details.")
# ========================================================================
# Class 13: VendorPaymentView
# ========================================================================
# In ui/pages.py, replace the VendorPaymentView class

class VendorPaymentView(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='vendorPayments')
        
        content_layout = QVBoxLayout(); self.main_layout.addLayout(content_layout)
        self.temp_invoice_docs, self.temp_challan_docs = [], []; self._payment_data_cache = {}
        content_layout.setContentsMargins(10, 10, 10, 10)

        # --- Top Info ---
        top_info_layout = QVBoxLayout()
        self.project_name_header_label = QLabel("<PROJECT NAME>"); font = self.project_name_header_label.font(); font.setPointSize(16); font.setBold(True); self.project_name_header_label.setFont(font)
        page_title_label = QLabel("VENDOR PAYMENTS"); font = page_title_label.font(); font.setPointSize(18); font.setBold(True); page_title_label.setFont(font)
        top_info_layout.addWidget(self.project_name_header_label); top_info_layout.addWidget(page_title_label)
        content_layout.addLayout(top_info_layout)
        
        # --- Main Splitter ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(main_splitter, 1)

        # --- Left Panel ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Entry Form
        entry_form_frame = QFrame(); entry_form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        entry_form_layout = QVBoxLayout(entry_form_frame)
        top_form_layout = QGridLayout()
        self.vendor_invoice_id_entry = QLineEdit(); self.vendor_challan_id_entry = QLineEdit(); self.price_entry = QLineEdit()
        self.payment_date_entry = QDateEdit(calendarPopup=True); self.payment_date_entry.setDisplayFormat("yyyy-MM-dd")
        top_form_layout.addWidget(QLabel("Vendor Invoice ID:"), 0, 0); top_form_layout.addWidget(self.vendor_invoice_id_entry, 0, 1)
        top_form_layout.addWidget(QLabel("Vendor Challan ID:"), 1, 0); top_form_layout.addWidget(self.vendor_challan_id_entry, 1, 1)
        top_form_layout.addWidget(QLabel("Price (INR):"), 0, 2); top_form_layout.addWidget(self.price_entry, 0, 3)
        top_form_layout.addWidget(QLabel("Payment Date:"), 1, 2); top_form_layout.addWidget(self.payment_date_entry, 1, 3)
        entry_form_layout.addLayout(top_form_layout)
        
        doc_uploaders_layout = QHBoxLayout()
        self.invoice_uploader_frame, self.invoice_doc_tree = self._create_doc_uploader("Vendor Invoice Document(s)", "invoice")
        self.challan_uploader_frame, self.challan_doc_tree = self._create_doc_uploader("Vendor Challan Document(s)", "challan")
        doc_uploaders_layout.addWidget(self.invoice_uploader_frame); doc_uploaders_layout.addWidget(self.challan_uploader_frame)
        entry_form_layout.addLayout(doc_uploaders_layout)

        add_payment_button = QPushButton("Add Vendor Payment"); add_payment_button.setObjectName("FinishButton"); add_payment_button.clicked.connect(self.add_vendor_payment)
        entry_form_layout.addWidget(add_payment_button, 0, Qt.AlignmentFlag.AlignRight)
        left_layout.addWidget(entry_form_frame)
        
        # History Frame
        history_frame = QFrame(); history_frame.setFrameShape(QFrame.Shape.StyledPanel)
        history_layout = QVBoxLayout(history_frame)
        history_layout.addWidget(QLabel("<b>Vendor Payment History</b>"))
        self.history_tree = QTreeWidget(); self.history_tree.setHeaderLabels(["Date", "Amount", "Invoice ID", "Challan ID"])
        self.history_tree.itemSelectionChanged.connect(self._on_payment_selected)
        history_layout.addWidget(self.history_tree)
        left_layout.addWidget(history_frame, 1)

        main_splitter.addWidget(left_panel)
        
        # --- Right Panel (Document Viewer) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("<b>Documents for Selected Payment</b>"))
        self.docs_tree = QTreeWidget(); self.docs_tree.setHeaderLabels(["Document", "Type"])
        self.docs_tree.itemDoubleClicked.connect(self._open_document_link)
        right_layout.addWidget(self.docs_tree)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([700, 300])

        # --- Navigation ---
        bottom_bar_layout = QHBoxLayout()
        back_button = QPushButton("<< BACK TO FINANCIALS"); back_button.clicked.connect(lambda: self.navigate_request.emit("FinancialDetailsView"))
        bottom_bar_layout.addWidget(back_button); bottom_bar_layout.addStretch(1)
        content_layout.addLayout(bottom_bar_layout)

    def on_show(self):
        super().on_show(); project = self.controller.current_project_data
        if not project: self.navigate_request.emit("HomeView"); return
        self.project_name_header_label.setText(project.get('projectName', '<PROJECT NAME>'))
        self.vendor_invoice_id_entry.clear(); self.vendor_challan_id_entry.clear(); self.price_entry.clear()
        self.payment_date_entry.setDate(datetime.date.today()); self.temp_invoice_docs.clear(); self.temp_challan_docs.clear()
        self._refresh_doc_tree('invoice'); self._refresh_doc_tree('challan'); self.refresh_history_list(); self._on_payment_selected()

    def refresh_history_list(self):
        self.history_tree.clear(); self._payment_data_cache.clear()
        payments = sorted(self.controller.current_project_data.get('vendorPayments', []), key=lambda p: p.get('paymentDate', ''))
        for payment in payments:
            date_str = payment.get('paymentDate'); display_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y") if date_str else "N/A"
            invoice_ref = payment.get('invoice', {}).get('refNo', '---'); challan_ref = payment.get('challan', {}).get('refNo', '---')
            item = QTreeWidgetItem([display_date, f"{payment.get('totalAmount', 0.0):,.2f}", invoice_ref, challan_ref])
            self.history_tree.addTopLevelItem(item); self._payment_data_cache[id(item)] = payment

    def _on_payment_selected(self):
        self.docs_tree.clear()
        selected_items = self.history_tree.selectedItems()
        if not selected_items: return
        
        payment_data = self._payment_data_cache.get(id(selected_items[0]))
        if not payment_data: return
        
        for doc in payment_data.get('invoice', {}).get('documents', []):
            item = QTreeWidgetItem([doc['name'], "Invoice"]); item.setData(0, Qt.ItemDataRole.UserRole, doc)
            item.setForeground(0, QBrush(QColor("#0969DA"))); item.setToolTip(0, "Double-click to open file")
            self.docs_tree.addTopLevelItem(item)

        for doc in payment_data.get('challan', {}).get('documents', []):
            item = QTreeWidgetItem([doc['name'], "Challan"]); item.setData(0, Qt.ItemDataRole.UserRole, doc)
            item.setForeground(0, QBrush(QColor("#0969DA"))); item.setToolTip(0, "Double-click to open file")
            self.docs_tree.addTopLevelItem(item)

    def add_vendor_payment(self):
        try: price = float(self.price_entry.text().strip()); assert price > 0
        except (ValueError, TypeError, AssertionError): QMessageBox.critical(self, "Input Error", "Please enter a valid, positive number for Price."); return
        new_payment = {"paymentDate": self.payment_date_entry.date().toString("yyyy-MM-dd"), "totalAmount": price,
                       "invoice": {"refNo": self.vendor_invoice_id_entry.text().strip(), "documents": list(self.temp_invoice_docs)},
                       "challan": {"refNo": self.vendor_challan_id_entry.text().strip(), "documents": list(self.temp_challan_docs)}}
        self.controller.current_project_data.setdefault('vendorPayments', []).append(new_payment)
        if self.controller.save_project_to_sqlite(self.controller.current_project_data): QMessageBox.information(self, "Success", "Vendor payment added."); self.on_show()
        else: self.controller.current_project_data['vendorPayments'].pop(); QMessageBox.critical(self, "Save Error", "Failed to save vendor payment.")

    def _open_document_link(self, item, column):
        doc_data = item.data(0, Qt.ItemDataRole.UserRole)
        project_folder = self.controller.current_project_data.get('projectFolderPath')
        if doc_data and project_folder and doc_data.get('path'):
            full_path = Path(project_folder) / doc_data['path']
            if full_path.exists(): QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))
            else: QMessageBox.warning(self, "File Not Found", f"Could not find file: {full_path}")
    
    # --- Other helper methods (_create_doc_uploader, _add_document, etc.) are unchanged ---
    def _create_doc_uploader(self, label_text, doc_type):
        frame = QFrame(); frame.setFrameShape(QFrame.Shape.StyledPanel); layout = QVBoxLayout(frame); layout.addWidget(QLabel(f"<b>{label_text}</b>"))
        buttons = QHBoxLayout(); add_btn = QPushButton("Add"); add_btn.clicked.connect(lambda: self._add_document(doc_type)); rem_btn = QPushButton("Remove"); rem_btn.clicked.connect(lambda: self._remove_document(doc_type))
        buttons.addWidget(add_btn); buttons.addWidget(rem_btn); buttons.addStretch(); layout.addLayout(buttons)
        tree = QTreeWidget(); tree.setHeaderHidden(True); tree.setFixedHeight(80); layout.addWidget(tree)
        return frame, tree
    def _add_document(self, doc_type):
        target_subfolder = SUBFOLDER_NAMES.get("vendorPayments", "Misc_Documents")
        self._handle_document_selection_for_tab(doc_type, target_subfolder, allow_multiple=True)
    def _remove_document(self, doc_type):
        temp_list_ref = self.temp_invoice_docs if doc_type == 'invoice' else self.temp_challan_docs; tree = self.invoice_doc_tree if doc_type == 'invoice' else self.challan_doc_tree
        if not tree.selectedItems(): return
        if QMessageBox.question(self, "Confirm", "Remove all staged documents for this type?") == QMessageBox.StandardButton.Yes: temp_list_ref.clear(); self._refresh_doc_tree(doc_type)
    def _refresh_doc_tree(self, doc_type):
        tree = self.invoice_doc_tree if doc_type == 'invoice' else self.challan_doc_tree; temp_list = self.temp_invoice_docs if doc_type == 'invoice' else self.temp_challan_docs
        tree.clear(); [tree.addTopLevelItem(QTreeWidgetItem([doc.get('name', 'N/A')])) for doc in temp_list]
    def _handle_document_selection_for_tab(self, doc_key_name, target_subfolder_name, allow_multiple=False):
        temp_list = self.temp_invoice_docs if doc_key_name == 'invoice' else self.temp_challan_docs
        filepaths, _ = QFileDialog.getOpenFileNames(self, "Select one or more documents");
        if not filepaths: return
        project_main_folder = self.controller.current_project_data.get('projectFolderPath')
        if not project_main_folder: QMessageBox.warning(self, "File Management", "Project folder path not set. Files cannot be copied."); return
        target_path = Path(project_main_folder) / target_subfolder_name; target_path.mkdir(parents=True, exist_ok=True)
        for fp_str in filepaths:
            original_file = Path(fp_str); destination_path = target_path / original_file.name
            try: shutil.copy2(original_file, destination_path); new_doc_data = {'name': original_file.name, 'path': str(destination_path.relative_to(project_main_folder)), 'type': 'project_file'}; temp_list.append(new_doc_data)
            except Exception as e: QMessageBox.critical(self, "File Copy Error", f"Could not copy file: {e}")
        self._refresh_doc_tree(doc_key_name)
# ========================================================================
# Class 14: FulfillmentView
# ========================================================================
class FulfillmentView(PageFrame):
    def __init__(self, controller):
        super().__init__(controller, page_data_key='fulfillmentDocs')
        
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)

        self.bom_item_widgets = []
        self.temp_docs = {}
        
        content_layout.setContentsMargins(10, 10, 10, 10)

        # --- Header ---
        header_layout = QVBoxLayout()
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font(); font.setPointSize(16); font.setBold(True)
        self.project_name_header_label.setFont(font)
        page_title_label = QLabel("Process BOM Fulfillment")
        font = page_title_label.font(); font.setPointSize(18); font.setBold(True)
        page_title_label.setFont(font)
        header_layout.addWidget(self.project_name_header_label)
        header_layout.addWidget(page_title_label)
        content_layout.addLayout(header_layout)
        
        # --- BOM Items Scroll Area ---
        bom_frame = QFrame(); bom_frame.setFrameShape(QFrame.Shape.StyledPanel)
        bom_frame_layout = QVBoxLayout(bom_frame)
        bom_frame_layout.addWidget(QLabel("<b>Select Items and Enter Quantity to Fulfill</b>"))
        self.bom_scroll_area = QScrollArea(); self.bom_scroll_area.setWidgetResizable(True)
        self.bom_scroll_content = QWidget()
        self.bom_items_layout = QVBoxLayout(self.bom_scroll_content)
        self.bom_items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bom_scroll_area.setWidget(self.bom_scroll_content)
        bom_frame_layout.addWidget(self.bom_scroll_area)
        content_layout.addWidget(bom_frame, 1)

        # --- Document Tabs ---
        self.doc_tab_view = QTabWidget()
        doc_definitions = {"officeTaxInvoice": "Office Tax Invoice", "deliveryChallan": "Office Delivery Challan", "installationCertificate": "Installation Certificate", "workCompletionCertificate": "Work Completion Certificate"}
        self.doc_tabs = {key: self._create_document_tab(title) for key, title in doc_definitions.items()}
        for key, tab_widget in self.doc_tabs.items():
            self.doc_tab_view.addTab(tab_widget, tab_widget.windowTitle())
        content_layout.addWidget(self.doc_tab_view, 1)

        # --- Bottom Bar ---
        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.addWidget(QLabel("<b>Fulfillment Date (for all entries):</b>"))
        self.fulfillment_date_entry = QDateEdit(calendarPopup=True)
        self.fulfillment_date_entry.setDisplayFormat("yyyy-MM-dd")
        bottom_bar_layout.addWidget(self.fulfillment_date_entry)
        bottom_bar_layout.addStretch()
        back_button = QPushButton("<< BACK")
        back_button.clicked.connect(lambda: self.navigate_request.emit("ProjectDetailsView"))
        submit_button = QPushButton("SUBMIT & SAVE FULFILLMENT")
        submit_button.setObjectName("FinishButton")
        submit_button.clicked.connect(self.submit_fulfillment)
        bottom_bar_layout.addWidget(back_button)
        bottom_bar_layout.addWidget(submit_button)
        content_layout.addLayout(bottom_bar_layout)

    def _create_document_tab(self, title):
        tab = QWidget()
        tab.setWindowTitle(title)
        layout = QVBoxLayout(tab)
        
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Ref No:"))
        ref_entry = QLineEdit()
        ref_layout.addWidget(ref_entry)
        layout.addLayout(ref_layout)
        tab.ref_entry = ref_entry

        if "Work Completion" in title:
            loc_layout = QHBoxLayout()
            loc_layout.addWidget(QLabel("Delivery location:"))
            loc_entry = QLineEdit()
            loc_layout.addWidget(loc_entry)
            layout.addLayout(loc_layout)
            tab.loc_entry = loc_entry

        button_layout = QHBoxLayout()
        doc_key = next(k for k, v in {"officeTaxInvoice": "Office Tax Invoice", "deliveryChallan": "Office Delivery Challan", "installationCertificate": "Installation Certificate", "workCompletionCertificate": "Work Completion Certificate"}.items() if v == title)
        add_btn = QPushButton("Add Document(s)"); add_btn.clicked.connect(lambda: self._add_document(doc_key))
        rem_btn = QPushButton("Remove Selected"); rem_btn.clicked.connect(lambda: self._remove_document(doc_key))
        button_layout.addWidget(add_btn); button_layout.addWidget(rem_btn); button_layout.addStretch()
        layout.addLayout(button_layout)
        
        doc_tree = QTreeWidget(); doc_tree.setHeaderHidden(True)
        layout.addWidget(doc_tree)
        tab.doc_tree = doc_tree
        return tab

    def on_show(self):
        super().on_show()
        project = self.controller.current_project_data
        if not project: self.navigate_request.emit("HomeView"); return
        
        self.project_name_header_label.setText(project.get('projectName', '<PROJECT NAME>'))
        
        for widget in self.bom_item_widgets: widget.deleteLater()
        self.bom_item_widgets.clear()
        
        self.temp_docs = {key: [] for key in self.doc_tabs.keys()}
        for key, tab in self.doc_tabs.items():
            tab.ref_entry.clear()
            if hasattr(tab, 'loc_entry'): tab.loc_entry.clear()
            self._refresh_doc_tree(key)
        
        self.fulfillment_date_entry.setDate(datetime.date.today())
        
        # Clear any old widgets from the layout
        while self.bom_items_layout.count():
            child = self.bom_items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        bom_items = project.get('billOfMaterials', {}).get('items', [])
        if not bom_items:
            self.bom_items_layout.addWidget(QLabel("No Bill of Materials items to fulfill."))
            return
        
        for item in bom_items:
            total_fulfilled_qty = sum(float(f.get('fulfilledQty', 0.0)) for f in item.get('fulfillments', []))
            remaining_qty = max(0.0, float(item.get('qty', 0.0)) - total_fulfilled_qty)
            
            item_frame = QFrame(); item_frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame_layout = QVBoxLayout(item_frame)
            frame_layout.addWidget(QLabel(f"<b>SL.{item.get('sl_no', '')} Item: {item.get('item', 'N/A')}</b>"))
            frame_layout.addWidget(QLabel(f"Original Qty: {item.get('qty', 0.0):.2f} | Fulfilled: {total_fulfilled_qty:.2f} | Remaining: {remaining_qty:.2f}"))
            
            if remaining_qty > 1e-9:
                entry_layout = QHBoxLayout()
                entry_layout.addWidget(QLabel("Fulfill Qty:"))
                qty_entry = QLineEdit(); qty_entry.setPlaceholderText(f"Max {remaining_qty:.2f}")
                entry_layout.addWidget(qty_entry)
                frame_layout.addLayout(entry_layout)
                item_frame.qty_entry = qty_entry
                item_frame.bom_item_ref = item
            else:
                frame_layout.addWidget(QLabel("FULLY FULFILLED", styleSheet="color: green;"))
                item_frame.qty_entry = None
                
            self.bom_items_layout.addWidget(item_frame)
            self.bom_item_widgets.append(item_frame)

    def submit_fulfillment(self):
        project = self.controller.current_project_data
        fulfillment_date = self.fulfillment_date_entry.date().toString("yyyy-MM-dd")
        has_new_fulfillment_entry = False

        for item_frame in self.bom_item_widgets:
            qty_entry = getattr(item_frame, 'qty_entry', None)
            if qty_entry and qty_entry.text().strip():
                try:
                    qty_to_fulfill = float(qty_entry.text().strip())
                    if qty_to_fulfill <= 1e-9: continue
                    bom_item_dict = item_frame.bom_item_ref
                    
                    # --- THIS IS THE MODIFIED PART ---
                    new_entry = {
                        "fulfillmentId": str(uuid.uuid4()), # Add a unique ID
                        "fulfilledQty": qty_to_fulfill,
                        "fulfilledDate": fulfillment_date,
                        "remarks": ""
                    }
                    bom_item_dict.setdefault('fulfillments', []).append(new_entry)
                    # --- END OF MODIFICATION ---
                    
                    has_new_fulfillment_entry = True
                except ValueError:
                    QMessageBox.critical(self, "Input Error", "Invalid quantity entered. Please use numbers only."); return
                

        fulfillment_docs_data = self._get_section_data()
        docs_added = False
        for key, tab in self.doc_tabs.items():
            ref_no = tab.ref_entry.text().strip()
            if ref_no or self.temp_docs[key]:
                doc_entry = {'refNo': ref_no, 'date': fulfillment_date, 'documents': self.temp_docs[key]}
                if hasattr(tab, 'loc_entry'):
                    doc_entry['deliveryLocation'] = tab.loc_entry.text().strip()
                fulfillment_docs_data.setdefault(key, []).append(doc_entry)
                docs_added = True

        if not has_new_fulfillment_entry and not docs_added:
            QMessageBox.warning(self, "No Data", "No new fulfillment quantities or documents were entered."); return

        self.controller.update_project_status(project)
        if self.controller.save_project_to_sqlite(project):
            QMessageBox.information(self, "Success", "Fulfillment details saved successfully!")
            self.navigate_request.emit("ProjectDetailsView")
        else:
            QMessageBox.critical(self, "Save Error", "Failed to save fulfillment details.")

    def _add_document(self, doc_key):
        target_subfolder = SUBFOLDER_NAMES.get("fulfillmentDocuments", "Misc_Documents")
        self._handle_document_selection_for_tab(doc_key, target_subfolder, allow_multiple=True)
        
    def _remove_document(self, doc_key):
        if QMessageBox.question(self, "Confirm", "Remove all staged documents for this type?") == QMessageBox.StandardButton.Yes:
            self.temp_docs[doc_key].clear()
            self._refresh_doc_tree(doc_key)
            
    def _refresh_doc_tree(self, doc_key):
        tree = self.doc_tabs[doc_key].doc_tree
        temp_list = self.temp_docs[doc_key]
        tree.clear()
        for doc in temp_list: tree.addTopLevelItem(QTreeWidgetItem([doc.get('name', 'N/A')]))
            
    def _handle_document_selection_for_tab(self, doc_key_name, target_subfolder_name, allow_multiple=False):
        temp_list = self.temp_docs[doc_key_name]
        filepaths, _ = QFileDialog.getOpenFileNames(self, "Select one or more documents")
        if not filepaths: return

        project_main_folder = self.controller.current_project_data.get('projectFolderPath')
        if not project_main_folder:
            QMessageBox.warning(self, "File Management", "Project folder path not set. Files cannot be copied."); return

        target_path = Path(project_main_folder) / target_subfolder_name
        target_path.mkdir(parents=True, exist_ok=True)
        
        for fp_str in filepaths:
            original_file = Path(fp_str)
            destination_path = target_path / original_file.name
            try:
                shutil.copy2(original_file, destination_path)
                new_doc_data = {'name': original_file.name, 'path': str(destination_path.relative_to(project_main_folder)), 'type': 'project_file'}
                temp_list.append(new_doc_data)
            except Exception as e:
                QMessageBox.critical(self, "File Copy Error", f"Could not copy file: {e}")
        
        self._refresh_doc_tree(doc_key_name)

# ========================================================================
# Class 15: ProjectCreationPreview (REVISED AND ENHANCED)
# ========================================================================

class ProjectCreationPreview(PageFrame):
    def __init__(self, controller):
        super().__init__(controller)
        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        content_layout.setContentsMargins(10, 10, 10, 10)

        header_layout = QVBoxLayout()
        self.project_name_header_label = QLabel("<PROJECT NAME>")
        font = self.project_name_header_label.font(); font.setPointSize(16); font.setBold(True)
        self.project_name_header_label.setFont(font)
        
        page_title_label = QLabel("PROJECT PREVIEW")
        font = page_title_label.font(); font.setPointSize(18); font.setBold(True)
        page_title_label.setFont(font)
        
        header_layout.addWidget(self.project_name_header_label)
        header_layout.addWidget(page_title_label)
        content_layout.addLayout(header_layout)

        self.preview_tree = QTreeWidget()
        self.preview_tree.setHeaderLabels(["Field", "Value"])
        self.preview_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.preview_tree.itemDoubleClicked.connect(self.handle_item_click)
        
        content_layout.addWidget(self.preview_tree, 1)

        nav_layout = self._create_navigation_buttons(back_page="HomeView", next_page_or_action=None, save_and_return_home=False)
        self.main_layout.addLayout(nav_layout)

    def handle_item_click(self, item, column):
        """Opens a file if a document item is double-clicked."""
        doc_data = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(doc_data, dict) and 'path' in doc_data:
            project_folder = self.controller.current_project_data.get('projectFolderPath')
            full_path = None
            if doc_data.get('type') == 'project_file' and project_folder:
                full_path = Path(project_folder) / doc_data['path']
            
            if full_path and full_path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))
            else:
                QMessageBox.warning(self, "File Not Found", f"Could not find file at path: {doc_data.get('path', 'N/A')}")
    
    def _get_bom_item_summary(self, item_dict):
        """Helper to calculate fulfilled/pending amounts for a BoM item."""
        if not isinstance(item_dict, dict): return {}
        fulfillments = item_dict.get('fulfillments', [])
        total_fulfilled_qty = sum(float(f.get('fulfilledQty', 0.0)) for f in fulfillments)
        original_qty = float(item_dict.get('qty', 0.0))
        pending_qty = max(0.0, original_qty - total_fulfilled_qty)
        original_total_value = float(item_dict.get('total', 0.0))
        value_per_unit = (original_total_value / original_qty) if original_qty > 1e-9 else 0
        fulfilled_value = total_fulfilled_qty * value_per_unit
        pending_value = pending_qty * value_per_unit
        return {
            'original_qty': original_qty,
            'original_total': original_total_value,
            'fulfilled_qty': total_fulfilled_qty,
            'fulfilled_value': fulfilled_value,
            'pending_qty': pending_qty,
            'pending_value': pending_value
        }

    def on_show(self):
        super().on_show()
        self.preview_tree.clear()
        
        project = self.controller.current_project_data
        if not project or not project.get('projectName'):
            self.project_name_header_label.setText("<NO PROJECT SELECTED>")
            return
            
        project_name = project.get('projectName', '<PROJECT NAME>')
        self.project_name_header_label.setText(project_name if project_name else "<NO PROJECT NAME>")

        def add_category(name):
            item = QTreeWidgetItem([name])
            font = item.font(0); font.setBold(True); item.setFont(0, font)
            item.setExpanded(True)
            self.preview_tree.addTopLevelItem(item)
            return item

        def add_row(parent, field, value):
            QTreeWidgetItem(parent, [str(field), str(value)])

        def add_docs(parent, field_name, doc_list):
            if not doc_list: return
            docs_item = QTreeWidgetItem(parent, [str(field_name), f"{len(doc_list)} document(s)"])
            for doc in doc_list:
                if isinstance(doc, dict):
                    doc_child = QTreeWidgetItem(docs_item, ["", doc.get('name', 'N/A')])
                    doc_child.setData(0, Qt.ItemDataRole.UserRole, doc)
                    doc_child.setForeground(1, QBrush(QColor("#0969DA")))
                    doc_child.setToolTip(1, "Double-click to open file")
            docs_item.setExpanded(False)

        # --- General Information ---
        gen_cat = add_category("General Information")
        add_row(gen_cat, "Project Name", project.get('projectName', 'N/A'))
        add_row(gen_cat, "Project Lead", project.get('projectLead', 'N/A'))
        
        # MODIFIED: Determine and display the project type
        project_type = "Normal"
        if project.get('isLimitedTenderProject'):
            project_type = "Limited Tender"
        elif project.get('isTenderProject'):
            project_type = "Open Tender"
        add_row(gen_cat, "Project Type", project_type)
        
        add_row(gen_cat, "Status", project.get('status', 'N/A'))
        add_row(gen_cat, "Project Folder", project.get('projectFolderPath', 'N/A'))

        # --- Department & Enquiry ---
        dept_cat = add_category("Department & Enquiry")
        dept_details = project.get('departmentDetails', {})
        add_row(dept_cat, "Department Name", dept_details.get('name', 'N/A'))
        add_row(dept_cat, "Memo ID", dept_details.get('memoId', 'N/A'))
        add_row(dept_cat, "Memo Date", dept_details.get('memoDate', 'N/A'))
        add_docs(dept_cat, "Enquiry Documents", project.get('departmentEnquiryDetails', {}).get('documents', []))

        # --- NEW: Conditional Tender Details Section ---
        if project_type != "Normal":
            tender_cat = add_category("Tender & Bidding Details")
            
            if project_type == "Limited Tender":
                ltd_details = project.get('limitedTenderDetails', {})
                add_docs(tender_cat, "Tender Notice Documents", ltd_details.get('tenderNoticeDocs', []))
                
                bidders_parent = QTreeWidgetItem(tender_cat, ["Bidders / Comparative Statement", f"{len(ltd_details.get('bidders', []))} participant(s)"])
                winner_name = ltd_details.get('winner')
                sorted_bidders = sorted(ltd_details.get('bidders', []), key=lambda b: b.get('price', float('inf')))

                for bidder in sorted_bidders:
                    is_winner = bidder.get('name') == winner_name
                    display_text = f"{bidder.get('name')} - Price: {bidder.get('price', 0):,.2f} INR {'✅ Winner' if is_winner else ''}"
                    bidder_item = QTreeWidgetItem(bidders_parent, [display_text, ""])
                    if is_winner:
                        font = bidder_item.font(0); font.setBold(True); bidder_item.setFont(0, font)
                    add_docs(bidder_item, "Submitted Documents", bidder.get('docs', []))

            elif project_type == "Open Tender":
                otd_details = project.get('tenderDetails', {})
                add_docs(tender_cat, "Tender Notice Documents", otd_details.get('tenderNoticeDocs', []))
                
                bidders_parent = QTreeWidgetItem(tender_cat, ["Bidders", f"{len(otd_details.get('bidders', []))} participant(s)"])
                winner_name = otd_details.get('qualifiedBidder')
                
                for bidder in otd_details.get('bidders', []):
                    is_winner = bidder.get('name') == winner_name
                    display_text = f"{bidder.get('name')} {'✅ Qualified Bidder' if is_winner else ''}"
                    bidder_item = QTreeWidgetItem(bidders_parent, [display_text, ""])
                    if is_winner:
                        font = bidder_item.font(0); font.setBold(True); bidder_item.setFont(0, font)
                    add_docs(bidder_item, "Submitted Documents", bidder.get('docs', []))

        # --- OEM & Vendor ---
        oem_cat = add_category("OEM & Vendor")
        oem_data = project.get('oemVendorDetails', {})
        add_row(oem_cat, "OEM Name", oem_data.get('oemName', 'N/A'))
        add_row(oem_cat, "Vendor Name", oem_data.get('vendorName', 'N/A'))
        add_docs(oem_cat, "OEM/Vendor Documents", oem_data.get('documents', []))

        # ... (rest of the method for Proposals, OEN, BOM, Financials, etc. is unchanged) ...
        # --- Proposals & Orders ---
        prop_cat = add_category("Proposals & Orders")
        prop_data = project.get('proposalOrderDetails', {})
        add_row(prop_cat, "Office Proposal ID", prop_data.get('officeProposalId', 'N/A'))
        add_row(prop_cat, "Proposal Date", prop_data.get('proposalDate', 'N/A'))
        add_docs(prop_cat, "Proposal Documents", prop_data.get('proposalDocuments', []))
        add_docs(prop_cat, "CEO Approval Documents", prop_data.get('ceoApprovalDocuments', []))
        add_row(prop_cat, "Dept. Work Order ID", prop_data.get('departmentWorkOrderId', 'N/A'))
        add_docs(prop_cat, "Work Order Documents", prop_data.get('workOrderDocuments', []))
        
        # --- OEN & Office Work Order ---
        oen_cat = add_category("OEN & Office Work Order")
        oen_data = project.get('oenDetails', {})
        add_row(oen_cat, "OEN Registration No", oen_data.get('oenRegistrationNo', 'N/A'))
        add_row(oen_cat, "Office OEN No", oen_data.get('officeOenNo', 'N/A'))
        add_docs(oen_cat, "OEN Documents", oen_data.get('documents', []))
        add_row(oen_cat, "Office Work Order ID", oen_data.get('officeWorkOrderId', 'N/A'))
        add_docs(oen_cat, "Office Work Order Documents", oen_data.get('officeWorkOrderDocuments', []))

        # --- Bill of Materials (REVISED TABLE FORMAT) ---
        bom = project.get('billOfMaterials', {})
        if bom.get('items'):
            bom_cat = add_category("Bill of Materials")
            for item in bom['items']:
                item_parent = QTreeWidgetItem(bom_cat, [f"Item #{item.get('sl_no')}", item.get('item')])
                add_row(item_parent, "HSN Code", item.get('hsn', 'N/A'))
                add_row(item_parent, "Specifications", item.get('specs', 'N/A'))
                add_row(item_parent, "Original Qty", f"{item.get('qty', 0.0):.2f}")
                add_row(item_parent, "Unit Price", f"{item.get('unitPrice', 0.0):,.2f}")
                add_row(item_parent, "GST %", f"{item.get('gstPercent', 0.0):.2f}%")
                add_row(item_parent, "Original Total Value", f"{item.get('total', 0.0):,.2f}")
                
                fulfillment_parent = QTreeWidgetItem(item_parent, ["Fulfillment Status", ""])
                summary = self._get_bom_item_summary(item)
                add_row(fulfillment_parent, "  - Fulfilled", f"Qty: {summary.get('fulfilled_qty', 0):.2f}, Value: {summary.get('fulfilled_value', 0):,.2f}")
                add_row(fulfillment_parent, "  - Pending", f"Qty: {summary.get('pending_qty', 0):.2f}, Value: {summary.get('pending_value', 0):,.2f}")
            add_row(bom_cat, "Total in Words", bom.get('amountInWords', 'N/A'))

        # --- Financials & Transactions ---
        fin_cat = add_category("Financials & Transactions")
        fin_data = project.get('financialDetails', {})
        client_payments = QTreeWidgetItem(fin_cat, ["Client Payments", f"{len(fin_data.get('transactions',[]))} transaction(s)"])
        for trans in fin_data.get('transactions', []):
            trans_text = f"{trans.get('transactionDetails')} (Amount: {trans.get('amountReceived', 0):,.2f})"
            trans_parent = QTreeWidgetItem(client_payments, [f"Paid on {trans.get('date')}", trans_text])
            add_docs(trans_parent, "Attached Files", trans.get('documents', []))
        
        vendor_payments = QTreeWidgetItem(fin_cat, ["Vendor Payments", f"{len(project.get('vendorPayments',[]))} transaction(s)"])
        for v_pay in project.get('vendorPayments', []):
            pay_text = f"Amount: {v_pay.get('totalAmount', 0):,.2f}"
            v_pay_parent = QTreeWidgetItem(vendor_payments, [f"Paid on {v_pay.get('paymentDate')}", pay_text])
            add_docs(v_pay_parent, "Invoice Docs", v_pay.get('invoice', {}).get('documents', []))
            add_docs(v_pay_parent, "Challan Docs", v_pay.get('challan', {}).get('documents', []))
            
        # --- Fulfillment Documents ---
        fulfillment_docs = project.get('fulfillmentDocs', {})
        doc_cat = add_category("Fulfillment Documents")
        doc_map = {"officeTaxInvoice": "Office Tax Invoices", "deliveryChallan": "Delivery Challans", "installationCertificate": "Installation Certificates", "workCompletionCertificate": "Work Completion Certificates"}
        for key, title in doc_map.items():
            if fulfillment_docs.get(key):
                doc_parent = QTreeWidgetItem(doc_cat, [title, ""])
                for doc_event in fulfillment_docs[key]:
                    event_text = f"Ref: {doc_event.get('refNo', 'N/A')} on {doc_event.get('date', 'N/A')}"
                    event_parent = QTreeWidgetItem(doc_parent, ["", event_text])
                    add_docs(event_parent, "Attached Files", doc_event.get('documents', []))

        self.preview_tree.expandAll()
        self.preview_tree.resizeColumnToContents(0)
     

        
# ========================================================================
# NEW CLASS: UserProfileView
# ========================================================================
class UserProfileView(PageFrame):
    def __init__(self, controller):
        super().__init__(controller)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.current_user_photo_pixmap = None

        title_label = QLabel("USER PROFILE")
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.main_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.main_layout.addSpacing(20)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(main_splitter, 1)

        # --- Left Panel: Profile Info ---
        profile_panel = QFrame(objectName="CardFrame")
        profile_layout = QVBoxLayout(profile_panel)
        
        details_layout = QGridLayout()
        details_layout.setColumnStretch(1, 1)
        
        details_layout.addWidget(QLabel("<b>Username:</b>"), 0, 0)
        self.username_entry = QLineEdit()
        details_layout.addWidget(self.username_entry, 0, 1)
        
        details_layout.addWidget(QLabel("<b>Full Name:</b>"), 1, 0)
        self.full_name_entry = QLineEdit()
        details_layout.addWidget(self.full_name_entry, 1, 1)

        details_layout.addWidget(QLabel("<b>Email:</b>"), 2, 0)
        self.email_entry = QLineEdit()
        details_layout.addWidget(self.email_entry, 2, 1)
        
        profile_layout.addLayout(details_layout)
        
        save_details_button = QPushButton("Save Details", clicked=self._save_user_details)
        profile_layout.addWidget(save_details_button, 0, Qt.AlignmentFlag.AlignRight)
        profile_layout.addSpacing(20)

        profile_layout.addWidget(QLabel("<b>Profile Photo:</b>"))
        photo_layout = QHBoxLayout()
        
        # --- CORRECTED WIDGET CREATION ---
        self.user_photo_display = QLabel()
        self.user_photo_display.setFixedSize(100, 100)
        self.user_photo_display.setScaledContents(True)
        self.user_photo_display.setStyleSheet("border: 1px solid gray; border-radius: 50px;")
        # --- END CORRECTION ---
        
        photo_buttons_layout = QVBoxLayout()
        photo_buttons_layout.addWidget(QPushButton("Upload", clicked=self._upload_profile_photo))
        photo_buttons_layout.addWidget(QPushButton("Clear", clicked=self._clear_image))
        
        photo_layout.addWidget(self.user_photo_display)
        photo_layout.addLayout(photo_buttons_layout)
        photo_layout.addStretch()
        profile_layout.addLayout(photo_layout)
        
        profile_layout.addWidget(QPushButton("Save Photo", clicked=self._save_profile_photo, objectName="FinishButton"), 0, Qt.AlignmentFlag.AlignRight)
        profile_layout.addStretch(1)
        main_splitter.addWidget(profile_panel)

        # --- Right Panel: Change Password ---
        password_panel = QFrame(objectName="CardFrame")
        password_layout = QVBoxLayout(password_panel)
        password_layout.addWidget(QLabel("<b>Change Password:</b>"))

        self.old_password_entry = self._create_labeled_password_entry(password_layout, "Old Password:")
        self.new_password_entry = self._create_labeled_password_entry(password_layout, "New Password:")
        self.confirm_password_entry = self._create_labeled_password_entry(password_layout, "Confirm New:")
        password_layout.addStretch(1)
        password_layout.addWidget(QPushButton("CHANGE PASSWORD", clicked=self._change_password, objectName="FinishButton"), 0, Qt.AlignmentFlag.AlignRight)
        main_splitter.addWidget(password_panel)

        self.main_layout.addLayout(self._create_navigation_buttons(back_page="HomeView", next_page_or_action=None))

    def _create_labeled_password_entry(self, parent_layout, label_text):
        layout = QHBoxLayout()
        entry = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel(label_text))
        layout.addWidget(entry)
        parent_layout.addLayout(layout)
        return entry

    def on_show(self):
        super().on_show()
        user_data = self.controller.current_user_data
        if not user_data:
            QMessageBox.critical(self, "Error", "No user data available.")
            self.navigate_request.emit("HomeView")
            return
        
        self.username_entry.setText(user_data.get('username', ''))
        self.full_name_entry.setText(user_data.get('full_name', ''))
        self.email_entry.setText(user_data.get('email', ''))
        
        self._load_profile_photo()
        self._clear_password_fields()

    def _load_profile_photo(self):
        user_photo_blob = self.controller.current_user_data.get('user_photo')
        if user_photo_blob:
            pixmap = utils.blob_to_qpixmap(user_photo_blob)
            self.user_photo_display.setPixmap(pixmap)
            self.current_user_photo_pixmap = pixmap
        else:
            self.user_photo_display.clear()
            self.current_user_photo_pixmap = None

    def _upload_profile_photo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg)")
        if file_path:
            pixmap = QPixmap(file_path).scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.user_photo_display.setPixmap(pixmap)
            self.current_user_photo_pixmap = pixmap

    def _clear_image(self):
        if QMessageBox.question(self, "Confirm", "Clear profile photo?") == QMessageBox.StandardButton.Yes:
            self.user_photo_display.clear()
            self.current_user_photo_pixmap = None

    def _save_profile_photo(self):
        user_id = self.controller.current_user_data.get('id')
        photo_blob = utils.qpixmap_to_blob(self.current_user_photo_pixmap)
        if utils.update_user_profile_image(self.controller.users_db_path, user_id, photo_blob):
            self.controller.current_user_data['user_photo'] = photo_blob
            self.controller._update_user_profile_ui()
            QMessageBox.information(self, "Success", "Profile photo updated!")
        else:
            QMessageBox.critical(self, "Error", "Failed to update profile photo.")

    def _save_user_details(self):
        user_id = self.controller.current_user_data.get('id')
        new_username = self.username_entry.text().strip()
        new_full_name = self.full_name_entry.text().strip()
        new_email = self.email_entry.text().strip()

        if not new_username:
            QMessageBox.warning(self, "Input Error", "Username cannot be empty.")
            return

        result = utils.update_user_details(self.controller.users_db_path, user_id, new_username, new_full_name, new_email)
        
        if result is True:
            self.controller.current_user_data['username'] = new_username
            self.controller.current_user_data['full_name'] = new_full_name
            self.controller.current_user_data['email'] = new_email
            self.controller._update_user_profile_ui()
            QMessageBox.information(self, "Success", "User details updated successfully!")
        elif result is None:
            QMessageBox.critical(self, "Save Error", f"The username '{new_username}' is already taken.")
        else:
            QMessageBox.critical(self, "Save Error", "An unexpected database error occurred.")

    def _clear_password_fields(self):
        self.old_password_entry.clear()
        self.new_password_entry.clear()
        self.confirm_password_entry.clear()

    def _change_password(self):
        user_id = self.controller.current_user_data.get('id')
        old_pass = self.old_password_entry.text()
        new_pass = self.new_password_entry.text()
        confirm_pass = self.confirm_password_entry.text()

        if not all([old_pass, new_pass, confirm_pass]):
            QMessageBox.warning(self, "Input Error", "All password fields are required.")
            return
        if new_pass != confirm_pass:
            QMessageBox.warning(self, "Password Mismatch", "New passwords do not match.")
            return

        current_hash = self.controller.current_user_data.get('password_hash')
        if not utils.check_password(current_hash, old_pass):
            QMessageBox.critical(self, "Authentication Failed", "Old password is incorrect.")
            return

        if utils.update_user_password(self.controller.users_db_path, user_id, new_pass):
            QMessageBox.information(self, "Success", "Password changed successfully!")
            self._clear_password_fields()
            self.controller.current_user_data['password_hash'] = utils.hash_password(new_pass)
        else:
            QMessageBox.critical(self, "Error", "Failed to change password.")

    def handle_save_and_return_home(self):
        self.navigate_request.emit("HomeView")

            
# ========================================================================
# Class 17: AdminDepartmentView (Corrected)
# ========================================================================
class AdminDepartmentView(PageFrame):
    def __init__(self, controller):
        super().__init__(controller)
        self.editing_dept_id = None

        content_layout = QVBoxLayout()
        self.main_layout.addLayout(content_layout)
        
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # --- Header ---
        title_label = QLabel("ADMIN: MANAGE DEPARTMENTS")
        font = title_label.font(); font.setPointSize(18); font.setBold(True)
        title_label.setFont(font)
        content_layout.addWidget(title_label)

        # --- Entry Form ---
        entry_form_frame = QFrame(); entry_form_frame.setFrameShape(QFrame.Shape.StyledPanel)
        entry_form_layout = QVBoxLayout(entry_form_frame)
        entry_form_layout.addWidget(QLabel("<b>Add/Edit Department</b>"))
        
        name_layout = QHBoxLayout()
        name_label = QLabel("Department Name:")
        name_label.setFixedWidth(150)
        name_layout.addWidget(name_label)
        self.dept_name_entry = QLineEdit()
        name_layout.addWidget(self.dept_name_entry)
        entry_form_layout.addLayout(name_layout)

        address_layout = QHBoxLayout()
        address_label = QLabel("Department Address:")
        address_label.setFixedWidth(150)
        address_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        address_layout.addWidget(address_label)
        self.dept_address_entry = QTextEdit()
        self.dept_address_entry.setFixedHeight(60)
        address_layout.addWidget(self.dept_address_entry)
        entry_form_layout.addLayout(address_layout)

        button_row_layout = QHBoxLayout()
        button_row_layout.addStretch(1)
        self.clear_form_button = QPushButton("Clear Form"); self.clear_form_button.clicked.connect(self._clear_form)
        self.update_dept_button = QPushButton("Update Selected"); self.update_dept_button.clicked.connect(self._update_department_action)
        self.add_dept_button = QPushButton("Add Department"); self.add_dept_button.clicked.connect(self._add_department_action)
        button_row_layout.addWidget(self.clear_form_button)
        button_row_layout.addWidget(self.update_dept_button)
        button_row_layout.addWidget(self.add_dept_button)
        entry_form_layout.addLayout(button_row_layout)
        content_layout.addWidget(entry_form_frame)
        
        # --- Department List ---
        list_frame = QFrame(); list_frame.setFrameShape(QFrame.Shape.StyledPanel)
        list_layout = QVBoxLayout(list_frame)
        self.department_tree = QTreeWidget()
        self.department_tree.setHeaderLabels(["ID", "Department Name", "Address"])
        self.department_tree.setColumnWidth(0, 50)
        self.department_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.department_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.department_tree.itemSelectionChanged.connect(self._on_department_select)
        list_layout.addWidget(self.department_tree)
        
        list_button_layout = QHBoxLayout()
        self.delete_dept_button = QPushButton("Delete Selected")
        self.delete_dept_button.setObjectName("ExitButton")
        self.delete_dept_button.clicked.connect(self._delete_department_action)
        self.refresh_dept_list_button = QPushButton("Refresh List")
        self.refresh_dept_list_button.clicked.connect(self._refresh_department_list)
        list_button_layout.addWidget(self.delete_dept_button)
        list_button_layout.addStretch(1)
        list_button_layout.addWidget(self.refresh_dept_list_button)
        list_layout.addLayout(list_button_layout)
        content_layout.addWidget(list_frame, 1)

        # --- Navigation ---
        # Note: save_and_return_home is set to False, so the button won't appear
        # on the bottom bar, but the menubar home button still calls this handler.
        nav_layout = self._create_navigation_buttons(back_page="HomeView", next_page_or_action=None, save_and_return_home=False)
        self.main_layout.addLayout(nav_layout)

    # --- NEW METHOD: Override handle_save_and_return_home for AdminDepartmentView ---
    def handle_save_and_return_home(self):
        """Overrides the PageFrame's method to simply navigate back to HomeView,
        as department changes are saved directly by its own buttons."""
        self.navigate_request.emit("HomeView") # Just go home

    def on_show(self):
        super().on_show()
        self._refresh_department_list()
        self._clear_form()
        
    def _refresh_department_list(self):
        self.department_tree.clear()
        self.departments = utils.get_all_departments_from_db(self.controller.departments_db_path)
        for dept in self.departments:
            item = QTreeWidgetItem([str(dept['id']), dept['name'], dept['address']])
            self.department_tree.addTopLevelItem(item)

    def _clear_form(self):
        self.department_tree.clearSelection()
        self.dept_name_entry.clear()
        self.dept_address_entry.clear()
        self.add_dept_button.setEnabled(True)
        self.update_dept_button.setEnabled(False)
        self.editing_dept_id = None

    def _on_department_select(self):
        selected_items = self.department_tree.selectedItems()
        if not selected_items:
            self._clear_form()
            return
        
        selected_item = selected_items[0]
        self.editing_dept_id = int(selected_item.text(0))
        self.dept_name_entry.setText(selected_item.text(1))
        self.dept_address_entry.setPlainText(selected_item.text(2))
        self.add_dept_button.setEnabled(False)
        self.update_dept_button.setEnabled(True)

    def _add_department_action(self):
        name = self.dept_name_entry.text().strip()
        address = self.dept_address_entry.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Department Name cannot be empty.")
            return
        
        added_id = utils.add_department_to_db(self.controller.departments_db_path, name, address)
        if added_id:
            QMessageBox.information(self, "Success", f"Department '{name}' added successfully.")
            self._clear_form()
            self._refresh_department_list()
        else:
            QMessageBox.critical(self, "Error", f"Failed to add department '{name}'. It might already exist.")

    def _update_department_action(self):
        if self.editing_dept_id is None: return
        name = self.dept_name_entry.text().strip()
        address = self.dept_address_entry.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Department Name cannot be empty.")
            return
        
        if utils.update_department_in_db(self.controller.departments_db_path, self.editing_dept_id, name, address):
            QMessageBox.information(self, "Success", f"Department '{name}' updated successfully.")
            self._clear_form()
            self._refresh_department_list()
        else:
            QMessageBox.critical(self, "Error", f"Failed to update department '{name}'. The name might already exist.")

    def _delete_department_action(self):
        selected_items = self.department_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a department to delete.")
            return

        reply = QMessageBox.question(self, "Confirm Deletion", f"Are you sure you want to delete the selected {len(selected_items)} department(s)?\nThis action cannot be undone and may fail if projects are linked to it.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        deleted_count = 0
        for item in selected_items:
            dept_id = int(item.text(0))
            if utils.delete_department_from_db(self.controller.departments_db_path, self.controller.db_path, dept_id):
                deleted_count += 1
        
        if deleted_count > 0:
            QMessageBox.information(self, "Success", f"{deleted_count} department(s) deleted successfully.")
        
        self._clear_form()
        self._refresh_department_list()

