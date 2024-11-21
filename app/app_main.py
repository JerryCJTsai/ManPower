import sys

from PyQt5.QtWidgets import QApplication

from view.manpower_view import MainView

if __name__ == "__main__":
    print("Jerry")
    app = QApplication(sys.argv)
    win = MainView()
    win.show()
    sys.exit(app.exec())

