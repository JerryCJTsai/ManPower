from PyQt5.QtWidgets import QApplication
from view.testview import *
import sys


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = DemoView()
    win.show()
    sys.exit(app.exec_())