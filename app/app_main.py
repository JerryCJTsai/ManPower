import sys

from PyQt5.QtWidgets import QApplication

from view.manpower_view import MainView

if __name__ == "__main__":
    app = QApplication(sys.argv)
    print("Hello, World !!!")
    win = MainView()
    win.show()
    sys.exit(app.exec())
