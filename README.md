<p align="center">
  <img src="logo.png" alt="WORKFLOW Logo" width="128">
</p>
<h1 align="center">WORKFLOW</h1>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/License-GPLv3-blue.svg">
  <img alt="Python Version" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python">
  <img alt="Framework" src="https://img.shields.io/badge/UI-PyQt6-41CD52?logo=qt">
</p>

<p align="center">
  <strong>A comprehensive desktop application for managing project workflows, from inception to fulfillment and financial tracking.</strong>
</p>

<p align="center">
  </p>

## ✨ Key Features

* **Complete Project Lifecycle**: Manage standard, tender, and limited-tender projects from initial inquiry and department memos to final work completion certificates.
* **Financial Tracking**: Keep a detailed record of client transactions and vendor payments to monitor project profitability in real-time.
* **Document Management**: Upload and link all relevant documents—from proposals and work orders to invoices and challans—directly to your projects.
* **User Management**: Secure user authentication with login, signup, profile locking, and customizable user profiles.
* **Cross-Platform**: A single codebase that runs as a native application on both **Windows** and **Linux**.
* **Custom Theming**: Switch between multiple light and dark themes to customize the application's appearance.
* **AI-Powered Summaries**: Leverage an offline, local LLM to generate intelligent summaries of complex project details.

## 📥 Downloads

You can download the latest pre-compiled version of WORKFLOW for your operating system from the **[Releases Page](https://github.com/Protik1810/WorkFlow/releases)**.

* **[Download for Windows (.exe)](https://github.com/Protik1810/WorkFlow/releases/latest/download/WORKFLOW_Setup_v2.0.0.exe)**


*(Note: You will need to upload your installer and AppImage files to the "Releases" section of your GitHub repository for these links to work.)*

## 🚀 Running from Source

To run the application from the source code, follow these steps:

1.  **Prerequisites**
    * Python 3.12
    * Git
    * For **Ubuntu/Linux**, install required system libraries:
        ```bash
        sudo apt-get update && sudo apt-get install python3-tk libxcb-cursor0
        ```

2.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Protik1810/WorkFlow.git]
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```

## 🛠️ Technologies Used

* **Backend**: Python
* **GUI**: PyQt6
* **Database**: SQLite
* **Installer (Windows)**: Inno Setup
* **Package (Linux)**: AppImage

## 📄 License

This project is licensed under the **GNU General Public License v3.0**.
