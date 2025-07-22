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
import shutil
from pathlib import Path
import copy # <-- IMPORT COPY
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, QFileDialog,
    QLabel, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from config import initial_project_data_template, SUBFOLDER_NAMES

class PageFrame(QWidget):
    """Base class for all page frames in the application using PyQt."""
    
    navigate_request = pyqtSignal(str)
    save_and_home_request = pyqtSignal()
    quit_request = pyqtSignal()

    def __init__(self, controller, page_data_key=None):
        super().__init__()
        # This standard object name allows QSS to style all pages consistently
        self.setObjectName("PageFrame")
        
        self.controller = controller
        self.page_data_key = page_data_key
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.project_name_header_label = None

    def on_show(self):
        if not self.controller.app_ready:
            return
            
        if self.controller.current_project_data is None:
            self.controller.current_project_data = copy.deepcopy(initial_project_data_template)

        if self.project_name_header_label:
            project_name = self.controller.current_project_data.get('projectName', '<NEW PROJECT>')
            self.project_name_header_label.setText(project_name if project_name else "<NEW PROJECT NAME>")

    def _get_section_data(self):
        if self.controller.current_project_data is None or self.page_data_key is None:
            return None
        
        if self.page_data_key not in self.controller.current_project_data or \
           not isinstance(self.controller.current_project_data[self.page_data_key], dict):
            template_section = initial_project_data_template.get(self.page_data_key, {})
            self.controller.current_project_data[self.page_data_key] = template_section.copy()
            
        return self.controller.current_project_data[self.page_data_key]

    def _create_navigation_buttons(self, back_page, next_page_or_action, save_and_return_home=True, finish_action_details=None):
        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(10, 10, 10, 10)

        if back_page:
            back_button = QPushButton("<< BACK")
            back_button.clicked.connect(lambda: self.navigate_request.emit(back_page))
            nav_layout.addWidget(back_button)

        if save_and_return_home:
            save_home_button = QPushButton("SAVE & RETURN HOME")
            save_home_button.setObjectName("SaveHomeButton")
            save_home_button.clicked.connect(self.handle_save_and_return_home)
            nav_layout.addWidget(save_home_button)

        nav_layout.addStretch(1)

        if next_page_or_action:
            next_button = QPushButton("NEXT >>")
            next_button.setObjectName("NextButton")
            if isinstance(next_page_or_action, str):
                # This line has been corrected to use the correct variable
                next_button.clicked.connect(lambda: self.handle_next(next_page_or_action))
            elif callable(next_page_or_action):
                next_button.clicked.connect(next_page_or_action)
            nav_layout.addWidget(next_button)

        if finish_action_details:
            finish_button = QPushButton(finish_action_details["text"])
            finish_button.setObjectName("FinishButton")
            finish_button.clicked.connect(finish_action_details["command"])
            nav_layout.addWidget(finish_button)

        exit_button = QPushButton("EXIT")
        exit_button.setObjectName("ExitButton")
        exit_button.clicked.connect(self.handle_exit)
        nav_layout.addWidget(exit_button)

        return nav_layout

    def handle_save_and_return_home(self):
        if hasattr(self, 'update_controller_project_data_from_form'):
            self.update_controller_project_data_from_form()
        if self.controller.current_project_data:
            if not self.controller.current_project_data.get('projectName', '').strip():
                 QMessageBox.critical(self, "Save Error", "Project Name cannot be empty to save and return home.")
                 return
            if self.controller.save_project_to_sqlite(self.controller.current_project_data):
                self.save_and_home_request.emit()
            else:
                QMessageBox.critical(self, "Save Error", "Failed to save project to database.")

    def handle_next(self, target_page):
        if hasattr(self, 'update_controller_project_data_from_form'):
            self.update_controller_project_data_from_form()
        if self.controller.current_project_data.get('id') is None:
            project_name = self.controller.current_project_data.get('projectName', '').strip()
            department_id = self.controller.current_project_data.get('departmentId')
            if self.page_data_key == 'departmentDetails' and not department_id:
                QMessageBox.critical(self, "Validation Error", "Please select a Department to proceed.")
                return
            if self.__class__.__name__ == 'NewProjectP1' and not project_name:
                QMessageBox.critical(self, "Validation Error", "Project Name cannot be empty to proceed.")
                return
        if not self.controller.current_project_data.get('id') and \
           self.controller.current_project_data.get('projectName'):
            self.controller.save_project_to_sqlite(self.controller.current_project_data)
        self.navigate_request.emit(target_page)

    def handle_exit(self):
        self.quit_request.emit()
    
    def _handle_document_selection(self, doc_key_name, display_label, target_subfolder_name, allow_multiple=False, target_dict=None, target_list=None):
        section_data = None
        if target_dict is not None:
            section_data = target_dict
        elif target_list is None:
            section_data = self._get_section_data()

        if section_data is None and target_list is None:
            QMessageBox.critical(self, "Data Error", "Cannot access the project data section to save documents.")
            return

        if allow_multiple:
            filepaths, _ = QFileDialog.getOpenFileNames(self, "Select one or more documents")
        else:
            filepath, _ = QFileDialog.getOpenFileName(self, "Select a single document")
            filepaths = [filepath] if filepath else []
        if not filepaths: return

        project_data = self.controller.current_project_data
        project_main_folder_str = project_data.get('projectFolderPath')
        
        if not project_main_folder_str and project_data.get('projectName'):
            created_path = self.controller.create_project_specific_folder(project_data)
            if created_path:
                project_main_folder_str = created_path
                project_data['projectFolderPath'] = created_path
                self.controller.save_project_to_sqlite(project_data)
            else:
                QMessageBox.warning(self, "File Management", "Could not create project folder. Files will be linked to original locations, but this is not recommended.")
                
        target_full_subfolder_path = None
        if project_main_folder_str:
            target_full_subfolder_path = Path(project_main_folder_str) / target_subfolder_name
            target_full_subfolder_path.mkdir(parents=True, exist_ok=True)
            
        if not allow_multiple and target_list is None: section_data.setdefault(doc_key_name, []).clear()
            
        files_processed_count = 0
        for original_filepath_str in filepaths:
            original_file = Path(original_filepath_str)
            new_doc_data = {}
            if target_full_subfolder_path:
                destination_path = target_full_subfolder_path / original_file.name
                if destination_path.exists():
                    reply = QMessageBox.question(self, "File Exists", f"The file '{original_file.name}' already exists. Overwrite?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No: continue
                try:
                    shutil.copy2(original_file, destination_path)
                    new_doc_data = {'name': original_file.name, 'path': str(destination_path.relative_to(project_main_folder_str)), 'type': 'project_file'}
                except Exception as e:
                    QMessageBox.critical(self, "File Copy Error", f"Could not copy file: {e}\nLinking to original location.")
                    new_doc_data = {'name': original_file.name, 'path': str(original_file), 'type': 'local_file_link_copy_failed'}
            else: new_doc_data = {'name': original_file.name, 'path': str(original_file), 'type': 'local_file_link'}

            if target_list is not None:
                target_list.append(new_doc_data)
            else:
                section_data.setdefault(doc_key_name, []).append(new_doc_data)
            files_processed_count += 1
            
        if files_processed_count > 0:
            if allow_multiple:
                if display_label:
                    display_label.setText(f"{len(target_list if target_list is not None else section_data[doc_key_name])} file(s) staged.")
                if hasattr(self, 'refresh_doc_tree'): self.refresh_doc_tree(doc_key_name)
                QMessageBox.information(self, "Documents Added", f"{files_processed_count} document(s) processed.")
            elif display_label:
                if target_list is not None:
                    last_doc_name = target_list[-1]['name']
                else:
                    last_doc_name = section_data[doc_key_name][-1]['name']
                display_label.setText(last_doc_name)