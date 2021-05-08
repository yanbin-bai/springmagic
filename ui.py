import os
import time
import inspect
import webbrowser
import urllib2
import random
import datetime
import maya.mel as mel
import pymel.core as pm

import springmagic.core as core

from shutil import copyfile


kSpringMagicVersion = 30500

scriptName = inspect.getframeinfo(inspect.currentframe()).filename
scriptPath = os.path.dirname(os.path.abspath(scriptName))

# Parameter Initialization
ui_file = scriptPath + os.sep + 'springMagic.ui'

# Constants
kPaypalLink = r'https://www.paypal.me/Yanbin'
kLinkedinLink = r'https://ca.linkedin.com/in/baiyanbin'
kVimeoLink = r''
kBilibiliLink = r'https://animbai.com/zh/2017/10/14/skintools-tutorials/'
kYoutubeLink = r'https://animbai.com/2017/10/14/skintools-tutorials/'

kUpdateLink = r'https://animbai.com/category/download/'
kVersionCheckLink = r'http://animbai.com/skintoolsver/'
kOldPersonalLink = r'http://www.scriptspot.com/3ds-max/scripts/spring-magic'


def widgetPath(windowName, widgetNames):
    """
    @param windowName: Window instance name to search
    @param widgetNames: list of names to search for
    """
    returnDict = {}
    mayaWidgetList = pm.lsUI(dumpWidgets=True)

    for widget in widgetNames:
        for mayaWidget in mayaWidgetList:
            if windowName in mayaWidget:
                if mayaWidget.endswith(widget):
                    returnDict[widget] = mayaWidget

    return returnDict

class SpringMagicWidget():

    def __init__(self, *args, **kwargs):
        self.init()

    def init(self):
        try:
            pm.deleteUI(self.ui)
        except:
            pass

        # title = pm.window(pm.loadUI(ui_file = ui_file))

        self.ui = pm.loadUI(f=ui_file)

        ui_widget_list = [
            'donatePayPal_button',
            'main_progressBar',
            'main_processLabel',
            'main_textEdit',
            'main_lang_id',
            'spring_language_list',
            'springSpring_lineEdit',
            'springSubs_lineEdit',
            'springXspring_lineEdit',
            'springTension_lineEdit',
            'springExtend_lineEdit',
            'springInertia_lineEdit',
            'springSubDiv_lineEdit',
            'springLoop_checkBox',
            'springPoseMatch_checkBox',
            'springClearSubFrame_checkBox',
            'springFrom_lineEdit',
            'springEnd_lineEdit',
            'springActive_radioButton',
            'springFrom_radioButton',
            # 'springUpAxis_comboBox',
            'springApply_Button',
            'springCapsule_checkBox',
            'springFastMove_checkBox',
            'springFloor_checkBox',
            'springFloor_lineEdit',
            'springBindPose_button',
            'springStraight_button',
            'springCopy_button',
            'springPaste_button',
            # 'donateBitcoin_lineEdit',
            'miscUpdate_pushButton',
            'springAddBody_Button',
            'springClearBody_Button',
            'springAddPlane_Button',
            'springAddWindCmd',
            'springBind_Button',
            'springBake_Button',
            'shelf_button',
            'link_pushButton',
            'vimeo_pushButton',
            'bilibili_pushButton',
            'language_button',
            'statusbar',
            'springWind_Button']

        self.uiObjects = widgetPath(self.ui, ui_widget_list)

        # Main UI
        self.main_progressBar = pm.progressBar(self.uiObjects['main_progressBar'], edit=True)
        self.main_processLabel = pm.text(self.uiObjects['main_processLabel'], edit=True)
        self.main_lineEdit = pm.ui.PyUI(self.uiObjects['main_textEdit'], edit=True)
        self.lang_id = pm.text(self.uiObjects['main_lang_id'], edit=True)

        self.language_list = pm.textScrollList(self.uiObjects['spring_language_list'], edit=True, selectCommand=self.languageSelectedCmd, visible=False)

        self.spring_lineEdit = pm.textField(self.uiObjects['springSpring_lineEdit'], edit=True, changeCommand=self.springRatioChangeCmd)
        self.subs_lineEdit = pm.textField(self.uiObjects['springSubs_lineEdit'], edit=True)
        self.Xspring_lineEdit = pm.textField(self.uiObjects['springXspring_lineEdit'], edit=True, changeCommand=self.twistChangeCmd)
        self.tension_lineEdit = pm.textField(self.uiObjects['springTension_lineEdit'], edit=True, changeCommand=self.tensionChangeCmd)
        self.extend_lineEdit = pm.textField(self.uiObjects['springExtend_lineEdit'], edit=True, changeCommand=self.extendChangeCmd)
        self.inertia_lineEdit = pm.textField(self.uiObjects['springInertia_lineEdit'], edit=True, changeCommand=self.inertiaChangeCmd)
        self.sub_division_lineEdit = pm.textField(self.uiObjects['springSubDiv_lineEdit'], edit=True, changeCommand=self.subDivChangeCmd)
        self.loop_checkBox = pm.checkBox(self.uiObjects['springLoop_checkBox'], edit=True)
        self.pose_match_checkBox = pm.checkBox(self.uiObjects['springPoseMatch_checkBox'], edit=True)
        self.clear_subframe_checkBox = pm.checkBox(self.uiObjects['springClearSubFrame_checkBox'], edit=True)
        self.from_lineEdit = pm.textField(self.uiObjects['springFrom_lineEdit'], edit=True)
        self.end_lineEdit = pm.textField(self.uiObjects['springEnd_lineEdit'], edit=True)
        self.active_radioButton = pm.radioButton(self.uiObjects['springActive_radioButton'], edit=True)
        self.from_radioButton = pm.radioButton(self.uiObjects['springFrom_radioButton'], edit=True)
        # self.upAxis_comboBox = pm.optionMenu(self.uiObjects['springUpAxis_comboBox'], edit=True)
        self.apply_button = pm.button(self.uiObjects['springApply_Button'], edit=True, command=self.applyCmd)
        self.add_body_button = pm.button(self.uiObjects['springAddBody_Button'], edit=True, command=self.addBodyCmd)
        self.clear_body_button = pm.button(self.uiObjects['springClearBody_Button'], edit=True, command=self.clearBodyCmd)
        self.add_plane_button = pm.button(self.uiObjects['springAddPlane_Button'], edit=True, command=self.createColPlaneCmd)
        self.wind_button = pm.button(self.uiObjects['springWind_Button'], edit=True, command=self.addWindCmd)
        self.bind_button = pm.button(self.uiObjects['springBind_Button'], edit=True, command=self.bindControlsCmd)
        self.bake_button = pm.button(self.uiObjects['springBake_Button'], edit=True, command=self.clearBindCmd)
        self.shelf_button = pm.button(self.uiObjects['shelf_button'], edit=True, command=self.goShelfCmd)
        self.link_button = pm.button(self.uiObjects['link_pushButton'], edit=True, command=self.linkinCmd)
        self.vimeo_button = pm.button(self.uiObjects['vimeo_pushButton'], edit=True, command=self.youtubeCmd)
        self.bilibili_button = pm.button(self.uiObjects['bilibili_pushButton'], edit=True, command=self.bilibiliCmd)
        self.language_button = pm.button(self.uiObjects['language_button'], edit=True, command=self.languageCmd)

        self.collision_checkBox = pm.checkBox(self.uiObjects['springCapsule_checkBox'], edit=True)
        self.fast_move_checkBox = pm.checkBox(self.uiObjects['springFastMove_checkBox'], edit=True)
        self.floor_checkBox = pm.checkBox(self.uiObjects['springFloor_checkBox'], edit=True)
        self.floor_lineEdit = pm.textField(self.uiObjects['springFloor_lineEdit'], edit=True, changeCommand=self.twistChangeCmd)

        self.bind_pose_button = pm.button(self.uiObjects['springBindPose_button'], edit=True, command=self.setCmd)
        self.straight_button = pm.button(self.uiObjects['springStraight_button'], edit=True, command=self.straightCmd)
        self.copy_button = pm.button(self.uiObjects['springCopy_button'], edit=True, command=self.copyCmd)
        self.paste_button = pm.button(self.uiObjects['springPaste_button'], edit=True, command=self.pasteCmd)

        # self.statusbar = pm.button(self.uiObjects['statusbar'], edit=True, menuItemCommand=self.testCmd)

        # donate UI
        # self.donate_bitcoin_lineEdit = pm.textField(self.uiObjects['donateBitcoin_lineEdit'], edit=True, text=kBitcoin)

        self.misc_update_button = pm.button(self.uiObjects['miscUpdate_pushButton'], edit=True, command=self.updatePageCmd)

        # SpringMagic_mainWindow11|centralwidget|miscUpdate_pushButton
        # SpringMagic_mainWindow11|centralwidget|miscUpdate_pushButton
        # 'miscUpdate_pushButton': ui.Button('SpringMagic_mainWindow11|centralwidget|miscUpdate_pushButton')
        # miscUpdate_button = pm.button( centralwidget + '|miscUpdate_pushButton', edit = True )

        pm.button(self.uiObjects['donatePayPal_button'], edit=True, command=self.donatePayPalCmd)

        self.spam_word = ['', '', '', '', '']

    def show(self):

        pm.showWindow(self.ui)

        self.checkUpdate()

    def progression_callback(self, progression):
        pm.progressBar(self.main_progressBar, edit=True, progress=progression)

    #############################################
    # Buttons callbacks
    ############################################

    def showSpam(self, *args):
        sWord = self.spam_word[random.randint(0, 4)]
        # print as unicode
        pm.text(self.main_processLabel, edit=True, label=unicode(sWord, "utf8", errors="ignore"))

    def linkinCmd(self, *args):
        # open my linked in page :)
        url = kLinkedinLink

        webbrowser.open(url, new=2)

    def pasteCmd(self, *args):
        core.pasteBonePose()

    def setCmd(self, *args):

        picked_bones = pm.ls(sl=1, type='joint')

        if picked_bones:
            self.apply_button.setEnable(False)

            core.bindPose()

            # Select only the joints
            pm.select(picked_bones)

            self.apply_button.setEnable(True)

    def straightCmd(self, *args):

        picked_bones = pm.ls(sl=1, type='joint')

        if picked_bones:
            self.apply_button.setEnable(False)

            for bone in picked_bones:
                core.straightBonePose(bone)

            # Select only the joints
            pm.select(picked_bones)

            self.apply_button.setEnable(True)

    def applyCmd(self, *args):
        picked_transforms = pm.ls(sl=1, type='transform')

        if picked_transforms:
            self.apply_button.setEnable(False)

            pm.text(self.main_processLabel, edit=True, label='Calculating Bone Spring... (Esc to cancel)')

            springRatio = 1 - float(self.spring_lineEdit.getText())
            twistRatio = 1 - float(self.Xspring_lineEdit.getText())
            isLoop = bool(self.loop_checkBox.getValue())
            isPoseMatch = bool(self.pose_match_checkBox.getValue())
            isFastMove = self.fast_move_checkBox.getValue()
            isCollision = self.collision_checkBox.getValue()

            subDiv = 1.0
            if isCollision:
                subDiv = float(self.sub_division_lineEdit.getText())

            # get frame range
            if self.active_radioButton.getSelect():
                startFrame = int(pm.playbackOptions(q=1, minTime=1))
                endFrame = int(pm.playbackOptions(q=1, maxTime=1))
            else:
                startFrame = int(self.from_lineEdit.getText())
                endFrame = int(self.end_lineEdit.getText())

            tension = float(self.tension_lineEdit.getText())
            inertia = float(self.inertia_lineEdit.getText())
            extend = float(self.extend_lineEdit.getText())

            wipeSubFrame = self.clear_subframe_checkBox.getValue()

            spring = core.Spring(springRatio, twistRatio, tension, extend, inertia)
            springMagic = core.SpringMagic(startFrame, endFrame, subDiv, isLoop, isPoseMatch, isCollision, isFastMove, wipeSubFrame)

            startTime = datetime.datetime.now()

            try:
                core.startCompute(spring, springMagic, self.progression_callback)

                deltaTime = (datetime.datetime.now() - startTime)

                pm.text(self.main_processLabel, edit=True, label="Spring Calculation Time: {0}s".format(deltaTime.seconds))

            except ValueError as exception:
                pm.text(self.main_processLabel, edit=True, label='Process aborted')
                pm.warning(exception)

            # Select only the joints
            pm.select(picked_transforms)

            pm.progressBar(self.main_progressBar, edit=True, progress=0)

            self.apply_button.setEnable(True)

    def copyCmd(self, *args):
        core.copyBonePose()

    def webCmd(self, *args):
        # open my linked in page :)
        webbrowser.open(kOldPersonalLink, new=2)

    def twistChangeCmd(self, *args):
        self.limitTextEditValue(self.Xspring_lineEdit, defaultValue=0.7)

    def extendChangeCmd(self, *args):
        self.limitTextEditValue(self.extend_lineEdit, defaultValue=0.0)

    def inertiaChangeCmd(self, *args):
        self.limitTextEditValue(self.inertia_lineEdit, defaultValue=0.0)

    def springRatioChangeCmd(self, *args):
        self.limitTextEditValue(self.spring_lineEdit, defaultValue=0.7)

    def tensionChangeCmd(self, *args):
        self.limitTextEditValue(self.tension_lineEdit, defaultValue=0.5)

    def subDivChangeCmd(self, *args):
        # self.limitTextEditValue(self.sub_division_lineEdit, defaultValue=1)
        pass

    def addWindCmd(self, *args):
        core.addWindObj()

    def addBodyCmd(self, *args):
        core.addCapsuleBody()

    def createColPlaneCmd(self, *args):
        core.createCollisionPlane()

    def removeBodyCmd(self, *args):
        core.removeBody(clear=False)

    def clearBodyCmd(self, *args):
        core.removeBody(clear=True)

    def bindControlsCmd(self, *args):
        core.bindControls()

    def clearBindCmd(self, *args):

        # get frame range
        if self.active_radioButton.getSelect():
            startFrame = int(pm.playbackOptions(q=1, minTime=1))
            endFrame = int(pm.playbackOptions(q=1, maxTime=1))
        else:
            startFrame = int(self.from_lineEdit.getText())
            endFrame = int(self.end_lineEdit.getText())

        core.clearBind(startFrame, endFrame)

    def goShelfCmd(self, *args):
        parentTab = mel.eval('''global string $gShelfTopLevel;string $shelves = `tabLayout -q -selectTab $gShelfTopLevel`;''')
        imageTitlePath = scriptPath + os.sep + "icons" + os.sep + "Title.png"
        # commandLine = "execfile(r'{0}\\springMagic.py')".format(self.scriptPath)
        commandLine = "try:\n\timport springmagic\n\tspringmagic.main()\nexcept:\n\texecfile(r'{0}\springMagic.py')".format(scriptPath)

        pm.shelfButton(commandRepeatable=True, image1=imageTitlePath, label="Spring Magic", parent=parentTab, command=commandLine)

    def languageCmd(self, *args):
        self.language_list.setVisible(not self.language_list.getVisible())

    def languageSelectedCmd(self, *args):
        self.language_list.setVisible(False)
        self.applyLanguage(int(self.language_list.getSelectIndexedItem()[0]))

    def bilibiliCmd(self, *args):
        try:
            webbrowser.open(kBilibiliLink, new=2)
        except:
            pass

    def youtubeCmd(self, *args):
        try:
            webbrowser.open(kYoutubeLink, new=2)
        except:
            pass

    def vimeoCmd(self, *args):
        # try:
        #     webbrowser.open(kVimeoLink, new=2)
        # except:
        #     pass
        pass

    def donatePayPalCmd(self, *args):
        try:
            webbrowser.open(kPaypalLink, new=2)
        except:
            pass

    def updatePageCmd(self, *args):
        try:
            webbrowser.open(kUpdateLink, new=2)
        except:
            pass

    def applyLanguage(self, lanId):
        lanDict = {1: '_chn', 2: '_eng', 3: '_jpn'}

        if lanId in lanDict.keys():
            # get new language ui file path
            new_ui_file = scriptPath + os.sep + os.path.basename(ui_file).split('.')[0] + lanDict[lanId] + '.' + os.path.basename(ui_file).split('.')[1]
            copyfile(new_ui_file, ui_file)

            # Reload interface
            self.init()
            self.show()

    def detectMayaLanguage(self):
        mayaLan = None
        try:
            mayaLan = os.environ['MAYA_UI_LANGUAGE']
        except:
            import locale
            mayaLan = locale.getdefaultlocale()[0]

        lanDict = {'zh_CN': 1, 'en_US': 2, 'ja_JP': 3}
        self.applyLanguage(lanDict[mayaLan])

    def printTextEdit(self, textEdit, inputString):
        ctime = time.ctime()
        ptime = ctime.split(' ')
        inputString = ptime[3] + '  -  ' + inputString
        pm.scrollField(textEdit, edit=True, insertionPosition=0, insertText=inputString + '\n')

    def checkUpdate(self):

        self.misc_update_button.setVisible(0)

        page_content = None

        site = kVersionCheckLink
        hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
               'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
               'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
               'Accept-Encoding': 'none',
               'Accept-Language': 'en-US,en;q=0.8',
               'Connection': 'keep-alive'}

        req = urllib2.Request(site, headers=hdr)

        try:
            page = urllib2.urlopen(req, timeout=5)
            page_content = page.read()
        except:
            print('checkUpdate failed')

        if page_content:
            if len(page_content.split('|springMagic|')) > 1:
                new_kSpringMagicVersion = int(page_content.split('|springMagic|')[1])

                if new_kSpringMagicVersion > kSpringMagicVersion:
                    self.misc_update_button.setVisible(1)

                self.spam_word = []

                prefix = '|spam'
                suffix = '|'

                if self.lang_id.getLabel() == 'chn':
                    suffix = 'chn|'

                self.spam_word = [page_content.split(prefix + str(i) + suffix)[1] for i in range(1, 6)]
        else:
            pm.text(self.main_processLabel, edit=True, label='Check update failed, try later.')

        self.showSpam()

    def limitTextEditValue(self, ui_object, minValue=0, maxValue=1, roundF=2, defaultValue=0):
        value = 0

        try:
            value = float(ui_object.getText())
            value = round(value, roundF)
            value = max(min(maxValue, value), minValue)
        except:
            value = defaultValue

        ui_object.setText(str(value))
