import os
import sys
import json
import signal
import subprocess

from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QLineEdit, QMessageBox, QLabel,
    QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtCore import QTimer, QUrl


import silent_task_runner.about as about
import silent_task_runner.modules.configure as configure 
from silent_task_runner.modules.resources import resource_path

from silent_task_runner.modules.wabout    import show_about_window
from silent_task_runner.desktop import create_desktop_file, create_desktop_directory, create_desktop_menu


# ---------- Path to config file ----------
CONFIG_PATH = os.path.join( os.path.expanduser("~"),
                            ".config", 
                            about.__package__, 
                            "config.json" )

DEFAULT_CONTENT = {
    # Window
    "window_width": 512,
    "window_height": 400,

    # Labels
    "label_title": "Title",
    "label_time": "Time (HH:MM)",
    "label_command": "Command",

    # Buttons
    "button_add": "Add Task",
    "button_update": "Update Selected",
    "button_remove": "Remove Selected",

    # Messages
    "msg_error_title": "Error",
    "msg_error_fill": "Fill all fields!",
    "msg_error_select": "Select a task!",

    # Tray menu
    "traymenu_open": "📖 Open",
    "traymenu_task": "📝 Open task file",
    "traymenu_configure": "📝 Open config file",
    "traymenu_about": "🌟 About",
    "traymenu_coffee": "☕ Buy me a coffee: TrucomanX",
    "traymenu_exit": "❌ Exit"
}

configure.verify_default_config(CONFIG_PATH, default_content=DEFAULT_CONTENT)
CONFIG = configure.load_config(CONFIG_PATH)

# ---------------------------------------

# ---------- Path to config file ----------
TASKS_PATH = os.path.join(  os.path.expanduser("~"),
                            ".config", 
                            about.__package__, 
                            "tasks.json" )


DEFAULT_TASKS_CONTENT = [
    {
        "title": "lock session",
        "time": "02:00",
        "command": "loginctl lock-session"
    }
]

if not os.path.exists(TASKS_PATH):
    os.makedirs(os.path.dirname(TASKS_PATH), exist_ok=True)
    with open(TASKS_PATH, "w") as f:
        json.dump(DEFAULT_TASKS_CONTENT, f, indent=4)

# ---------------------------------------

def load_tasks():
    try:
        with open(TASKS_PATH, "r") as f:
            return json.load(f)
    except:
        return []


def save_tasks(tasks):
    with open(TASKS_PATH, "w") as f:
        json.dump(tasks, f, indent=4)


class Scheduler(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(about.__program_name__)
        self.resize(CONFIG["window_width"], CONFIG["window_height"])
        
        ## Icon
        # Get base directory for icons
        self.icon_path = resource_path("icons", "logo.png")
        self.setWindowIcon(QIcon(self.icon_path))

        self.tasks = load_tasks()
        self.last_run = {}

        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.load_task)
        layout.addWidget(self.list_widget)

        layout.addWidget(QLabel(CONFIG["label_title"]))
        self.title_input = QLineEdit()
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel(CONFIG["label_time"]))
        self.time_input = QLineEdit()
        layout.addWidget(self.time_input)

        layout.addWidget(QLabel(CONFIG["label_command"]))
        self.command_input = QLineEdit()
        layout.addWidget(self.command_input)

        add_btn = QPushButton(CONFIG["button_add"])
        add_btn.clicked.connect(self.add_task)
        layout.addWidget(add_btn)

        update_btn = QPushButton(CONFIG["button_update"])
        update_btn.clicked.connect(self.update_task)
        layout.addWidget(update_btn)

        remove_btn = QPushButton(CONFIG["button_remove"])
        remove_btn.clicked.connect(self.remove_task)
        layout.addWidget(remove_btn)

        self.setLayout(layout)
        self.refresh_list()

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_tasks)
        self.timer.start(20000)

    def refresh_list(self):
        self.list_widget.clear()
        for t in self.tasks:
            self.list_widget.addItem(f"{t['time']} - {t['title']}")

    def load_task(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            task = self.tasks[row]
            self.title_input.setText(task["title"])
            self.time_input.setText(task["time"])
            self.command_input.setText(task["command"])

    def add_task(self):
        title = self.title_input.text()
        time = self.time_input.text()
        command = self.command_input.text()

        if not title or not time or not command:
            QMessageBox.warning(self, CONFIG["msg_error_title"], CONFIG["msg_error_fill"])
            return

        self.tasks.append({
            "title": title,
            "time": time,
            "command": command
        })

        save_tasks(self.tasks)
        self.refresh_list()
        self.clear_inputs()

    def update_task(self):
        row = self.list_widget.currentRow()

        if row < 0:
            QMessageBox.warning(self, CONFIG["msg_error_title"], CONFIG["msg_error_select"])
            return

        self.tasks[row] = {
            "title": self.title_input.text(),
            "time": self.time_input.text(),
            "command": self.command_input.text()
        }

        save_tasks(self.tasks)
        self.refresh_list()
        self.clear_inputs()

    def remove_task(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.tasks.pop(row)
            save_tasks(self.tasks)
            self.refresh_list()
            self.clear_inputs()

    def clear_inputs(self):
        self.title_input.clear()
        self.time_input.clear()
        self.command_input.clear()

    def check_tasks(self):
        now = datetime.now().strftime("%H:%M")

        for i, task in enumerate(self.tasks):
            last = self.last_run.get(i)

            if task["time"] == now and last != now:
                subprocess.Popen(task["command"], shell=True)
                self.last_run[i] = now

    # 👇 NÃO fecha, só esconde
    def closeEvent(self, event):
        event.ignore()
        self.hide()


class TrayApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        self.window = Scheduler()

        # Get base directory for icons
        self.icon_path = resource_path("icons", "logo.png")

        self.tray_icon = QSystemTrayIcon(QIcon(self.icon_path), self)
        self.tray_icon.setVisible(True)
        self.setProperty("tray_icon", self.tray_icon)

        # Menu
        self.tray_menu = QMenu()

        ########################################################################
        ########################################################################
        self.open_action = QAction(CONFIG["traymenu_open"])
        self.open_action.triggered.connect(self.show_window)
        self.tray_menu.addAction(self.open_action)

        self.tray_menu.addSeparator()

        ########################################################################
        ########################################################################

        self.edit_task_action = QAction(QIcon.fromTheme("applications-utilities"), CONFIG["traymenu_task"], self)
        self.edit_task_action.triggered.connect(self.open_task_editor)
        self.tray_menu.addAction(self.edit_task_action)

        self.edit_config_action = QAction(QIcon.fromTheme("applications-utilities"), CONFIG["traymenu_configure"], self)
        self.edit_config_action.triggered.connect(self.open_configure_editor)
        self.tray_menu.addAction(self.edit_config_action)

        self.coffee_action = QAction(QIcon.fromTheme("emblem-favorite"), CONFIG["traymenu_coffee"], self)
        self.coffee_action.triggered.connect(self.on_coffee_action_click)
        self.tray_menu.addAction(self.coffee_action)
        
        self.about_action = QAction(QIcon.fromTheme("help-about"), CONFIG["traymenu_about"], self)
        self.about_action.triggered.connect(self.open_about)
        self.tray_menu.addAction(self.about_action)

        self.tray_menu.addSeparator()
        
        ########################################################################
        ########################################################################

        self.exit_action = QAction(CONFIG["traymenu_exit"])
        self.exit_action.triggered.connect(self.exit_app)
        self.tray_menu.addAction(self.exit_action)

        self.tray_icon.setContextMenu(self.tray_menu)

        self.tray_icon.show()

    def show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def exit_app(self):
        self.tray_icon.hide()
        self.quit()

    def _open_file_in_text_editor(self, filepath):
        if os.path.exists(filepath):
            if os.name == 'nt':  # Windows
                os.startfile(filepath)
            elif os.name == 'posix':  # Linux/macOS
                subprocess.run(['xdg-open', filepath])
            
    def open_configure_editor(self):
        self._open_file_in_text_editor(CONFIG_PATH)

    def open_task_editor(self):
        self._open_file_in_text_editor(TASKS_PATH)

    def open_about(self):
        data = {
            "version": about.__version__,
            "package": about.__package__,
            "program_name": about.__program_name__,
            "author": about.__author__,
            "email": about.__email__,
            "description": about.__description__,
            "url_source": about.__url_source__,
            "url_doc": about.__url_doc__,
            "url_funding": about.__url_funding__,
            "url_bugs": about.__url_bugs__
        }
        show_about_window(data, self.icon_path)

    def on_coffee_action_click(self):
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/trucomanx"))


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    '''
    create_desktop_directory()    
    create_desktop_menu()
    create_desktop_file(os.path.join("~",".local","share","applications"), 
                        program_name=about.__program_name__)
    
    for n in range(len(sys.argv)):
        if sys.argv[n] == "--autostart":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file(os.path.join("~",".config","autostart"), 
                                overwrite=True, 
                                program_name=about.__program_name__)
            return
        if sys.argv[n] == "--applications":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file(os.path.join("~",".local","share","applications"), 
                                overwrite=True, 
                                program_name=about.__program_name__)
            return
    '''
    app = TrayApp(sys.argv)
    app.setApplicationName(about.__package__)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
