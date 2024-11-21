from PyQt5.QtWidgets import QMainWindow

from pyui.main_ui import Ui_MainWindow


class MainView(QMainWindow, Ui_MainWindow):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

