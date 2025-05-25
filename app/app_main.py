from PyQt5.QtGui import QStandardItemModel, QStandardItem, QColor, QBrush
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QProgressDialog, QMessageBox
import sys
import configparser
import json
from jira import JIRA
import app_init

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

        #暫時跳過Jira登入
        config = configparser.ConfigParser()
        config.read('./ManPowerTool.ini')
        server = config['JIRA']['server']
        api_token = config['JIRA']['api_token']
        department = config['JIRA']['project_key']

        # 直接模擬登入成功
        #self.mbLogin = True

        # 暫時跳過Jira登入_取消註解恢復原本

        config = configparser.ConfigParser()
        config.read('./ManPowerTool.ini')
        server = config['JIRA']['server']
        api_token = config['JIRA']['api_token']
        department = config['JIRA']['project_key']

        try:
            jira = JIRA(server=server, token_auth=api_token, max_retries=0)
            user = jira.current_user()
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

        # 1. 確認Jira連線狀態
        if not self.mbLogin:
            QMessageBox.warning(self, "提示", "Jira尚未連線，請確認")
            return

        # 2. 執行 app_init.py，產生最新 workhour.json
        
        # bypass Jira test

        # 跳出提示視窗，阻止使用者操作，直到關閉
        progress = QProgressDialog("資料抓取中：0%", None, 0, 100, self)
        progress.setWindowTitle("Progess")
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setValue(0)

        # 隱藏 X 與 ? 按鈕
        flags = progress.windowFlags()
        flags &= ~Qt.WindowCloseButtonHint  # 移除 X
        flags &= ~Qt.WindowContextHelpButtonHint  # 移除 ?
        progress.setWindowFlags(flags)

        progress.show()
        progress.resize(350, progress.height())
        parent_geom = self.geometry()
        progress_geom = progress.frameGeometry()
        center_point = parent_geom.center()
        progress_geom.moveCenter(center_point)
        progress.move(progress_geom.topLeft())
        QApplication.processEvents()

        # 定義 callback 更新進度條
        def on_progress_update(current, total):
            percent = int(current * 100 / total) if total else 0
            progress.setValue(percent)
            progress.setLabelText(f"資料抓取中：{percent}%")
            QApplication.processEvents()

        try:
            app_init.main(progress_callback=on_progress_update)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Jira Error", f"執行 app_init 發生錯誤：\n{e}\n請檢查網路或聯絡IT人員")
            return

        progress.setValue(100)
        progress.close()

        #設定表頭樣式
        self.ui.tvShowMembersManHours.setShowGrid(True)
        self.ui.tvShowMembersManHours.setStyleSheet("""
        QTableView::horizontalHeader {
            border-bottom: 2px solid #888;
        }
        QTableView {
            gridline-color: #888;
        }
        QHeaderView::section {
            background-color: #ADADAD;
            color: #000;
            font-weight: bold;
        }
        """)

        # 3. 讀取 workhour.json
        with open('workhour.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        members = [m['name'] for m in data['members']]
        self.mModel.setVerticalHeaderLabels(members)

        #顯示周別
        zh_titles = ["本周", "下周", "下下周"]
        headers = [f"{zh_titles[i]}({w['wh_week_id']})" for i, w in enumerate(data['week'])]
        self.mModel.setHorizontalHeaderLabels(headers)

        # 取得每週的上限/下限工時(預設40/24)
        uplimits = [w.get('wh_week_uplimit_hours', 40) for w in data['week']]
        downlimits = [w.get('wh_week_downlimit_hours', 24) for w in data['week']]

        for row, m in enumerate(data['members']):
            week_hours = [m.get('week_1_hours', 0), m.get('week_2_hours', 0), m.get('week_3_hours', 0)]
            for col, h in enumerate(week_hours):
                item = QStandardItem(str(h))
                item.setTextAlignment(Qt.AlignRight)
                # 動態判斷上/下限
                if h > uplimits[col]:
                    item.setForeground(QBrush(QColor(30, 144, 255)))  # 超過上限
                elif h < downlimits[col]:
                    item.setForeground(QBrush(QColor(176, 23, 31)))  # 低於下限
                self.mModel.setItem(row, col, item)

    # 點擊人員時的按鍵動作
    def clickedMembers(self, item):
        if 'members' in self.mjMembersData:
            print(self.mjMembersData['members'][item.row()]['name'])


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = Demo()
    win.show()
    sys.exit(app.exec_())
