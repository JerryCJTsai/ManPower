from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor, QBrush
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt
import sys
import configparser
import json
from jira import JIRA

# 顯示 main_ui
from main_ui import *

class Demo(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.mbLogin = False
        self.initSetup()

        self.ui.lblLogin.setAlignment(Qt.AlignCenter)   #設定登入顯示狀態
        if self.mbLogin:
            self.ui.lblLogin.setText("已登入")
            self.ui.lblLogin.setStyleSheet('''
                        border-radius: 10px;
                        font-size: 11px;
                        color: #FFF;
                        background-color: rgb(48, 128, 20);
                    ''')

        else:
            self.ui.lblLogin.setText("未登入")
            self.ui.lblLogin.setStyleSheet('''
                        border-radius: 10px;
                        font-size: 11px;
                        color: #FFF;
                        background-color: #E3170D;
                    ''')


        #設定buttonGroup
        self.ui.buttonGroup.setId(self.ui.rbOriginAlgo, 1)
        self.ui.buttonGroup.setId(self.ui.rbModAlgo, 2)
        self.ui.buttonGroup.buttonClicked.connect(self.getSelectedAlgorithm)

        # 設定 Model
        self.mModel = QStandardItemModel(3, 3)
        self.mModel.setHorizontalHeaderLabels(['本周', '下周', '下下周'])
        self.ui.tvShowMembersManHours.setModel(self.mModel)
        self.ui.pbGenRefreshData.clicked.connect(self.generateAndRefresh)
        self.ui.tvShowMembersManHours.clicked.connect(self.clickedMembers)

    def initSetup(self):
        config = configparser.ConfigParser()
        config.read('./ManPowerTool.ini')
        server = config['JIRA']['server']
        # server = 'https://jira.XXXX.com'
        api_token = config['JIRA']['api_token']
        # api_token = '123'
        department = config['JIRA']['project_key']

        try:
            jira = JIRA(server=server, token_auth=api_token, max_retries=0)

            # 顯示使用者名稱
            user = jira.current_user()
            # print(f"Logged in as: {user}")
            if user != None or user != '':
                self.mbLogin = True
            else:
                self.mbLogin = False
        except:
            self.mbLogin = False

        #部門顯示
        self.ui.lblDepartment.setAlignment(Qt.AlignCenter)
        self.ui.lblDepartment.setText(department)
        self.ui.lblDepartment.setStyleSheet('''
                        border-radius: 12px;
                        font-size: 12px;
                        font-weight: bold;
                        color: #FFF;
                        background-color: rgb(9, 111, 227);
                    ''')
    # 選擇計算方式
    def getSelectedAlgorithm(self):
        if self.ui.buttonGroup.checkedId() == 1:
            print("Selected Origin Algorithm !!")
        elif self.ui.buttonGroup.checkedId() == 2:
            print("Selected Modified Algorithm !!!")

    # 產生資訊及更新
    def generateAndRefresh(self):
        with open('workhour.json', 'r') as f:
            text = f.read()
            f.close()
        data = json.loads(text)
        self.mModel.setHorizontalHeaderLabels(
            ['本周(' + str(data['week_1']) + ')', '下周(' + str(data['week_2']) + ')', '下下周(' + str(data['week_3']) + ')'])

        members = [data['members'][i]['name'] for i in range(len(data['members']))]
        self.mModel.setVerticalHeaderLabels(members)

        for row in range(len(members)):
            for column in range(1, 4):
                hours = data["members"][row]['week_' + str(column) + '_hours']

                item = QStandardItem(str(hours))
                item.setTextAlignment(Qt.AlignRight)
                # item.setFont(QFont("", 11, QFont.Black))

                if hours > 40:
                    item.setForeground(QBrush(QColor(30, 144, 255)))
                elif hours < 24:
                    item.setForeground(QBrush(QColor(176, 23, 31)))

                self.mModel.setItem(row, column - 1, item)

    # 點擊人員時的按鍵動作
    def clickedMembers(self, item):
        if 'members' in self.mjMembersData:
            print(self.mjMembersData['members'][item.row()]['name'])


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = Demo()
    win.show()
    sys.exit(app.exec_())
