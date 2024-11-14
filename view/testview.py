from PyQt5.QtWidgets import QMainWindow
from pyui.test import *

class DemoView(QMainWindow, Ui_MainWindow):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)