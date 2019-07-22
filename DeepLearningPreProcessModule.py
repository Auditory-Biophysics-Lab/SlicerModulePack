import inspect
import qt
import slicer
import SimpleITK as sitk
import sitkUtils as sitku
import Elastix
from slicer.ScriptedLoadableModule import *

# custom imports
import uiTools


# Main Initialization & Info
class DeepLearningPreProcessModule(ScriptedLoadableModule):
    """
    Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Temporal Bone Deep-Learning Pre-Process"
        self.parent.categories = ["Otolaryngology"]
        self.parent.dependencies = ["SlicerElastix"]
        self.parent.contributors = ["Luke Helpard (Western University) and Evan Simpson (Western University)"]
        self.parent.helpText = """
        
            """
        self.parent.helpText += self.getDefaultModuleDocumentationLink()
        self.parent.acknowledgementText = "This file was originally developed by Luke Helpard and Evan Simpson at" \
                                          "the University of Western Ontario. "


# User Interface
class DeepLearningPreProcessModuleWidget(ScriptedLoadableModuleWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
    # Data members --------------
    atlasNode = None
    atlasFiducialNode = None
    inputNode = None
    inputFiducialNode = None
    fiducialSet = []
    outputNode = None

    # UI members --------------
    sectionsList = []
    # input
    inputSelector = None
    fitAllButton = None
    leftBoneCheckBox = None
    rightBoneCheckBox = None
    # resampling
    resamplingInfoLabel = None
    resampleSpacingXBox = None
    resampleSpacingYBox = None
    resampleSpacingZBox = None
    resampleButton = None
    # fiducials
    fiducialPlacer = None
    fiducialTabs = None
    fiducialTabsLastIndex = None
    fiducialApplyButton = None
    fiducialOverlayCheckbox = None
    fiducialHardenButton = None
    # rigid
    rigidApplyButton = None
    # output
    outputLabel = None
    outputSelector = None

    # TODO remove
    # cropButton = None
    # defineROIButton = None
    # flipButton = None
    # outputSelector = None

    # main initialization ------------------------------------------------------------------------------
    def __init__(self, parent):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.init_input_tools()
        self.init_resample_tools()
        self.init_fiducial_registration()
        self.init_rigid_registration()
        self.init_output_tools()

    def init_input_tools(self):
        self.inputSelector = slicer.qMRMLNodeComboBox()
        self.inputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.inputSelector.selectNodeUponCreation = True
        self.inputSelector.addEnabled = False
        self.inputSelector.renameEnabled = True
        self.inputSelector.noneEnabled = True
        self.inputSelector.setMRMLScene(slicer.mrmlScene)
        self.inputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.click_load_volume)
        self.inputSelector.setToolTip("Select an existing input volume. If the volume's name start with numbers followed by an 'L' or an 'R', the side will be automatically selected.")
        path = slicer.os.path.dirname(slicer.os.path.abspath(inspect.getfile(inspect.currentframe()))) + '/Resources/Icons/fit.png'
        icon = qt.QPixmap(path).scaled(qt.QSize(16, 16), qt.Qt.KeepAspectRatio, qt.Qt.SmoothTransformation)
        self.fitAllButton = qt.QToolButton()
        self.fitAllButton.setIcon(qt.QIcon(icon))
        self.fitAllButton.setFixedHeight(22)
        self.fitAllButton.enabled = False
        self.fitAllButton.setToolTip("Fit all Slice Viewers to match the extent of the lowest non-Null volume layer.")
        self.fitAllButton.connect('clicked(bool)', self.click_fit_all_views)
        self.leftBoneCheckBox = qt.QCheckBox("Left Temporal Bone")
        self.leftBoneCheckBox.checked = False
        self.leftBoneCheckBox.connect('toggled(bool)', self.click_left_bone)
        self.rightBoneCheckBox = qt.QCheckBox("Right Temporal Bone")
        self.rightBoneCheckBox.checked = False
        self.rightBoneCheckBox.connect('toggled(bool)', self.click_right_bone)

    def init_resample_tools(self):
        self.resamplingInfoLabel = qt.QLabel("Load in a sample to enable spacing resample.")
        self.resampleSpacingXBox = uiTools.spin_box(0, 1000, self.click_spacing_spin_box)
        self.resampleSpacingYBox = uiTools.spin_box(0, 1000, self.click_spacing_spin_box)
        self.resampleSpacingZBox = uiTools.spin_box(0, 1000, self.click_spacing_spin_box)
        self.resampleButton = qt.QPushButton("Resample Input to New Volume")
        self.resampleButton.setFixedHeight(23)
        self.resampleButton.enabled = False
        self.resampleButton.connect('clicked(bool)', self.click_resample_volume)

    def init_fiducial_registration(self):
        self.fiducialTabs = qt.QTabWidget()
        self.fiducialTabs.setIconSize(qt.QSize(16, 16))
        self.fiducialTabs.connect('currentChanged(int)', self.click_fiducial_tab)
        self.fiducialApplyButton = qt.QPushButton("Apply")
        self.fiducialApplyButton.connect('clicked(bool)', self.click_fiducial_apply)
        self.fiducialApplyButton.enabled = False
        self.fiducialOverlayCheckbox = qt.QCheckBox("Overlay")
        self.fiducialOverlayCheckbox.connect('toggled(bool)', self.click_fiducial_overlay)
        self.fiducialOverlayCheckbox.enabled = False
        self.fiducialHardenButton = qt.QPushButton("Harden")
        self.fiducialHardenButton.connect('clicked(bool)', self.click_fiducial_harden)
        self.fiducialHardenButton.enabled = False
        self.fiducialPlacer = slicer.qSlicerMarkupsPlaceWidget()
        self.fiducialPlacer.buttonsVisible = False
        self.fiducialPlacer.placeMultipleMarkups = slicer.qSlicerMarkupsPlaceWidget.ForcePlaceSingleMarkup
        self.fiducialPlacer.setMRMLScene(slicer.mrmlScene)
        self.fiducialPlacer.placeButton().show()
        self.fiducialPlacer.connect('activeMarkupsFiducialPlaceModeChanged(bool)', self.click_fiducial_place_mode)

    def init_rigid_registration(self):
        self.rigidApplyButton = qt.QPushButton("Apply\n Rigid Registration")
        self.rigidApplyButton.connect('clicked(bool)', self.click_rigid_apply)

    def init_output_tools(self):
        self.outputLabel = qt.QLabel("No transformations applied to output node.")
        self.outputSelector = slicer.qMRMLNodeComboBox()
        self.outputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.outputSelector.selectNodeUponCreation = True
        self.outputSelector.addEnabled = True
        self.outputSelector.renameEnabled = True
        self.outputSelector.noneEnabled = False
        self.outputSelector.setMRMLScene(slicer.mrmlScene)
        # self.outputSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.click_load_volume)

    # TODO remove
    # def init_crop_tools(self):
    #     self.defineROIButton = qt.QPushButton("Define ROI")
    #     self.defineROIButton.enabled = True
    #     self.cropButton = qt.QPushButton("Crop")
    #     self.cropButton.enabled = True
    #
    # def init_flip_tools(self):
    #     self.flipButton = qt.QPushButton("Flip Volume")
    #     self.flipButton.enabled = False
    #     self.flipButton.connect('clicked(bool)', self.click_flip_volume)
    #
    # def init_output_tools(self):
    #     self.outputSelector = slicer.qMRMLNodeComboBox()
    #     self.outputSelector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
    #     self.outputSelector.selectNodeUponCreation = True
    #     self.outputSelector.addEnabled = False
    #     self.outputSelector.removeEnabled = False
    #     self.outputSelector.noneEnabled = True
    #     self.outputSelector.showHidden = False
    #     self.outputSelector.showChildNodeTypes = False
    #     self.outputSelector.setMRMLScene(slicer.mrmlScene)

    # main ui layout building ------------------------------------------------------------------------------
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.sectionsList.append(self.build_input_tools())
        self.sectionsList.append(self.build_resample_tools())
        self.sectionsList.append(self.build_fiducial_registration())
        self.sectionsList.append(self.build_rigid_registration())
        self.sectionsList.append(self.build_output_tools())
        for s in self.sectionsList: self.layout.addWidget(s)
        self.layout.addStretch()

        # testing TODO remove
        # path = slicer.os.path.dirname(slicer.os.path.abspath(inspect.getfile(inspect.currentframe()))) + "/Resources/Atlases/1512R_Clinical_Aligned_Test_Input.nrrd"
        # node = slicer.util.loadVolume(path, returnNode=True)[1]
        # self.inputSelector.setCurrentNode(node)
        # self.click_load_volume()
        # end testing area

    def build_input_tools(self):
        section = uiTools.dropdown("Input Selection")
        layout = qt.QFormLayout(section)
        layout.addRow(qt.QLabel("Select an input volume to begin, then ensure the correct side is selected."))
        box = qt.QHBoxLayout()
        box.addWidget(self.inputSelector)
        box.addWidget(self.fitAllButton)
        layout.addRow("Input Volume: ", box)
        sideSelection = qt.QHBoxLayout()
        sideSelection.addWidget(self.leftBoneCheckBox)
        sideSelection.addWidget(self.rightBoneCheckBox)
        layout.addRow("Side Selection: ", sideSelection)
        layout.setMargin(10)
        return section

    def build_resample_tools(self):
        section = uiTools.dropdown("Spacing Resample Tools", disabled=True)
        grid = qt.QGridLayout()
        label = qt.QLabel("X:")
        label.setAlignment(qt.Qt.AlignCenter)
        grid.addWidget(label, 0, 0, 1, 1)
        grid.addWidget(self.resampleSpacingXBox, 0, 1, 1, 1)
        label = qt.QLabel("um    Y:")
        label.setAlignment(qt.Qt.AlignCenter)
        grid.addWidget(label, 0, 3, 1, 1)
        grid.addWidget(self.resampleSpacingYBox, 0, 4, 1, 1)
        label = qt.QLabel("um    Z:")
        label.setAlignment(qt.Qt.AlignCenter)
        grid.addWidget(label, 0, 5, 1, 1)
        grid.addWidget(self.resampleSpacingZBox, 0, 6, 1, 1)
        label = qt.QLabel("um")
        label.setAlignment(qt.Qt.AlignCenter)
        grid.addWidget(label, 0, 7, 1, 1)
        grid.addWidget(self.resampleButton, 0, 8, 1, 20)
        layout = qt.QVBoxLayout(section)
        layout.addWidget(self.resamplingInfoLabel)
        layout.addLayout(grid)
        layout.setMargin(10)
        return section

    def build_fiducial_registration(self):
        section = uiTools.dropdown("Fiducial Registration", disabled=True)
        layout = qt.QVBoxLayout(section)
        layout.addWidget(qt.QLabel("Set at least 3 fiducials. Setting all 5 yields the best results."))
        layout.addWidget(self.fiducialTabs)
        row = qt.QHBoxLayout()
        row.addWidget(self.fiducialApplyButton)
        row.addWidget(self.fiducialOverlayCheckbox)
        row.addWidget(self.fiducialHardenButton)
        layout.addLayout(row)
        layout.setMargin(10)
        return section

    def build_rigid_registration(self):
        section = uiTools.dropdown("Rigid Registration", disabled=True)
        row = qt.QHBoxLayout()
        # row.addWidget(qt.QLabel("0.01 sample percentage\n30000 iterations\n0.00001 minimum step length"))
        # row.addWidget(qt.QLabel("2 maximum step length\n1 translation scale\n"))
        # row.addWidget(qt.QLabel("'normalized correlation' cost metric\n0.7 relaxation factor.\n"))
        layout = qt.QVBoxLayout(section)
        layout.addLayout(row)
        layout.addWidget(self.rigidApplyButton)
        layout.setMargin(10)
        return section

    def build_output_tools(self):
        section = uiTools.dropdown("Output Tools", disabled=True)
        layout = qt.QFormLayout(section)
        layout.addRow(self.outputLabel)
        layout.addRow("Output Volume: ", self.outputSelector)
        layout.setMargin(10)
        return section

    # TODO remove
    # def build_crop_dropdown(self):
    #     dropdown = ctk.ctkCollapsibleButton()
    #     dropdown.text = "Crop Tools"
    #     layout = qt.QFormLayout(dropdown)
    #     layout.addRow(self.defineROIButton)
    #     layout.addRow(self.cropButton)
    #     layout.setMargin(10)
    #     return dropdown
    #
    # def build_flip_tools(self):
    #     dropdown = ctk.ctkCollapsibleButton()
    #     dropdown.text = "Flip Volume"
    #     layout = qt.QFormLayout(dropdown)
    #     layout.addRow(self.flipButton)
    #     layout.setMargin(10)
    #     return dropdown
    #
    # def build_output_tools(self):
    #     dropdown = ctk.ctkCollapsibleButton()
    #     dropdown.text = "Output"
    #     layout = qt.QFormLayout(dropdown)
    #     layout.addRow("Output Volume: ", self.outputSelector)
    #     layout.setMargin(10)
    #     return dropdown

    # state checking ------------------------------------------------------------------------------
    def check_input_complete(self):
        if self.inputNode is not None and (self.leftBoneCheckBox.isChecked() or self.rightBoneCheckBox.isChecked()):
            self.update_sections(enabled=True)
            self.finalize_input()
            self.update_slicer_view()
        else:
            self.update_sections(enabled=False)

    # input complete - fetch atlas, fiducials, and populate table
    # TODO move to logic?
    def finalize_input(self):
        side_indicator = 'R' if self.rightBoneCheckBox.isChecked() else 'L'
        # check if side has been switched
        if self.atlasNode is not None and not self.atlasNode.GetName().startswith('Atlas_' + side_indicator):
            self.atlasNode = self.inputFiducialNode = None
        # check if we need an atlas imported
        if self.atlasNode is None:
            self.atlasNode, self.atlasFiducialNode = DeepLearningPreProcessModuleLogic().load_atlas_and_fiducials(side_indicator)
            self.fiducialSet = DeepLearningPreProcessModuleLogic().initialize_fiducial_set(self.atlasFiducialNode)
            self.fiducialTabs.clear()
            for f in self.fiducialSet:
                tab, f["table"] = uiTools.build_fiducial_tab(f, self.click_fiducial_set_button)
                self.fiducialTabs.addTab(tab, f["label"])
        # check if we need a fiducial node
        if self.inputFiducialNode is None:
            self.inputFiducialNode = slicer.vtkMRMLMarkupsFiducialNode()
            self.inputFiducialNode.SetName("Fiducial Input")
            slicer.mrmlScene.AddNode(self.inputFiducialNode)
            self.fiducialPlacer.setCurrentNode(self.inputFiducialNode)
        # init the output node as a copy of input
        self.outputNode = DeepLearningPreProcessModuleLogic().initialize_output_volume(self.inputNode)
        self.outputSelector.setCurrentNode(self.outputNode)

    # UI updating ------------------------------------------------------------------------------
    def update_sections(self, enabled):
        self.fitAllButton.enabled = enabled
        for i in range(1, len(self.sectionsList)):
            self.sectionsList[i].enabled = enabled
            self.sectionsList[i].collapsed = not enabled

    def update_slicer_view(self):
        # set 3 over 3 view
        slicer.app.layoutManager().setLayout(21)
        # update input and atlas slice views
        if self.inputNode is not None:
            volume_id = self.inputNode.GetID()
            slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetSliceCompositeNode().SetBackgroundVolumeID(volume_id)
            slicer.app.layoutManager().sliceWidget("Yellow").sliceLogic().GetSliceCompositeNode().SetBackgroundVolumeID(volume_id)
            slicer.app.layoutManager().sliceWidget("Green").sliceLogic().GetSliceCompositeNode().SetBackgroundVolumeID(volume_id)
        if self.atlasNode is not None:
            volume_id = self.atlasNode.GetID()
            slicer.app.layoutManager().sliceWidget("Red+").sliceLogic().GetSliceCompositeNode().SetBackgroundVolumeID(volume_id)
            slicer.app.layoutManager().sliceWidget("Yellow+").sliceLogic().GetSliceCompositeNode().SetBackgroundVolumeID(volume_id)
            slicer.app.layoutManager().sliceWidget("Green+").sliceLogic().GetSliceCompositeNode().SetBackgroundVolumeID(volume_id)
        self.click_fit_all_views()

    def update_fiducial_table(self):
        completed = 0
        path = slicer.os.path.dirname(slicer.os.path.abspath(inspect.getfile(inspect.currentframe()))) + '/Resources/Icons/'
        for i in range(0, len(self.fiducialSet)):
            if self.fiducialSet[i]['input_indices'] != [0, 0, 0]: completed += 1
            if self.fiducialPlacer.placeModeEnabled and i == self.fiducialTabs.currentIndex: icon = qt.QIcon(path + 'fiducial.png')
            else: icon = qt.QIcon(path + 'check.png') if self.fiducialSet[i]['input_indices'] != [0, 0, 0] else qt.QIcon()
            self.fiducialTabs.setTabIcon(i, icon)
        self.fiducialApplyButton.enabled = True if completed >= 3 else False

    def update_rigid_progress(self, text):
        print(text)
        slicer.app.processEvents()  # force update

    def update_output(self):
        pass

    # ui button actions ------------------------------------------------------------------------------
    def click_load_volume(self):
        self.inputNode = self.inputSelector.currentNode()
        if self.inputNode is None: return self.check_input_complete()
        # check for side selection
        for c in self.inputNode.GetName():
            if c.isdigit(): continue
            if c.isalpha():
                if c.upper() == 'R': self.click_right_bone(force=True)
                if c.upper() == 'L': self.click_left_bone(force=True)
            break
        # set spacing
        spacing = DeepLearningPreProcessModuleLogic().get_um_spacing(self.inputNode.GetSpacing())
        self.resamplingInfoLabel.text = "The input volume was imported with a spacing of (X: " + str(spacing[0]) + "um,  Y: " + str(spacing[1]) + "um,  Z: " + str(spacing[2]) + "um)"
        self.resampleSpacingXBox.value, self.resampleSpacingYBox.value, self.resampleSpacingZBox.value = spacing[0], spacing[1], spacing[2]
        # update state
        self.check_input_complete()

    def click_fit_all_views(self):
        logic = slicer.app.layoutManager().mrmlSliceLogics()
        for i in range(logic.GetNumberOfItems()): logic.GetItemAsObject(i).FitSliceToAll()
        if self.fiducialSet is not None and len(self.fiducialSet) > 0: self.click_fiducial_tab(self.fiducialTabs.currentIndex)

    def click_right_bone(self, force=False):
        if force: self.rightBoneCheckBox.setChecked(True)
        if self.rightBoneCheckBox.isChecked(): self.leftBoneCheckBox.setChecked(False)
        self.check_input_complete()

    def click_left_bone(self, force=False):
        if force: self.leftBoneCheckBox.setChecked(True)
        if self.leftBoneCheckBox.isChecked(): self.rightBoneCheckBox.setChecked(False)
        self.check_input_complete()

    def click_spacing_spin_box(self):
        if self.inputNode is None: return
        currentSpacing = DeepLearningPreProcessModuleLogic().get_um_spacing(self.inputNode.GetSpacing())
        boxSpacing = [self.resampleSpacingXBox.value, self.resampleSpacingYBox.value, self.resampleSpacingZBox.value]
        self.resampleButton.enabled = currentSpacing != boxSpacing

    def click_resample_volume(self):
        self.resampleButton.enabled = False
        spacing = [float(self.resampleSpacingXBox.value)/1000, float(self.resampleSpacingYBox.value)/1000, float(self.resampleSpacingZBox.value)/1000]
        resampledNode = DeepLearningPreProcessModuleLogic().pull_node_resample_push(self.inputNode, spacing)
        # TODO maybe remove and add a table?
        # TODO update output
        self.inputSelector.setCurrentNode(resampledNode)
        self.click_load_volume()

    def click_fiducial_tab(self, index):
        if self.fiducialPlacer.placeModeEnabled: self.fiducialPlacer.setPlaceModeEnabled(False)
        ras = self.fiducialSet[index]['atlas_indices']
        slicer.app.layoutManager().sliceWidget("Red+").sliceView().mrmlSliceNode().JumpSlice(ras[0], ras[1], ras[2])
        slicer.app.layoutManager().sliceWidget("Yellow+").sliceView().mrmlSliceNode().JumpSlice(ras[0], ras[1], ras[2])
        slicer.app.layoutManager().sliceWidget("Green+").sliceView().mrmlSliceNode().JumpSlice(ras[0], ras[1], ras[2])

    def click_fiducial_set_button(self, fiducial):
        for i in range(0, self.inputFiducialNode.GetNumberOfFiducials()):
            if self.inputFiducialNode.GetNthFiducialLabel(i) == fiducial["label"]:
                self.inputFiducialNode.RemoveMarkup(i)
                break
        self.fiducialPlacer.setPlaceModeEnabled(True)

    def click_fiducial_place_mode(self, placing):
        if placing: self.fiducialTabsLastIndex = self.fiducialTabs.currentIndex
        if not placing and self.fiducialTabsLastIndex == self.fiducialTabs.currentIndex:
            self.fiducialTabsLastIndex = None
            fiducial = self.fiducialSet[self.fiducialTabs.currentIndex]
            nodeIndex = self.inputFiducialNode.GetNumberOfFiducials() - 1
            self.inputFiducialNode.SetNthFiducialLabel(nodeIndex, fiducial["label"])
            self.inputFiducialNode.GetNthFiducialPosition(nodeIndex, fiducial["input_indices"])
            for i in (range(0, 3)): fiducial["table"].item(0, i).setText(fiducial["input_indices"][i])
        self.update_fiducial_table()

    def click_fiducial_apply(self):
        try:
            slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
            self.fiducialApplyButton.setEnabled(False)
            output, self.outputNode = DeepLearningPreProcessModuleLogic().apply_fiducial_registration(self.inputNode, self.outputNode, self.atlasFiducialNode, self.inputFiducialNode)
        except Exception as e:
            # print(e)
            self.update_rigid_progress("Error: {0}".format(e))
            import traceback
            traceback.print_exc()
        finally:
            slicer.app.restoreOverrideCursor()
            self.fiducialApplyButton.setEnabled(True)
            # display overlay
            slicer.app.layoutManager().sliceWidget('Red').sliceLogic().GetSliceCompositeNode().SetForegroundVolumeID(self.outputNode.GetID())
            slicer.app.layoutManager().sliceWidget('Yellow').sliceLogic().GetSliceCompositeNode().SetForegroundVolumeID(self.outputNode.GetID())
            slicer.app.layoutManager().sliceWidget('Green').sliceLogic().GetSliceCompositeNode().SetForegroundVolumeID(self.outputNode.GetID())
            self.fiducialOverlayCheckbox.setEnabled(True)
            self.fiducialOverlayCheckbox.setChecked(True)
            self.click_fiducial_overlay()
            self.fiducialHardenButton.setEnabled(True)

    def click_fiducial_overlay(self):
        o = 0.4 if self.fiducialOverlayCheckbox.isChecked() else 0
        slicer.app.layoutManager().sliceWidget('Red').sliceLogic().GetSliceCompositeNode().SetForegroundOpacity(o)
        slicer.app.layoutManager().sliceWidget('Yellow').sliceLogic().GetSliceCompositeNode().SetForegroundOpacity(o)
        slicer.app.layoutManager().sliceWidget('Green').sliceLogic().GetSliceCompositeNode().SetForegroundOpacity(o)

    def click_fiducial_harden(self):
        try:
            slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
            self.fiducialHardenButton.setEnabled(False)
            DeepLearningPreProcessModuleLogic().harden_fiducial_registration(self.outputNode)
        except Exception as e:
            # print(e)
            self.update_rigid_progress("Error: {0}".format(e))
            import traceback
            traceback.print_exc()
        finally:
            slicer.app.restoreOverrideCursor()

    def click_rigid_apply(self):
        try:
            slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
            self.outputNode = DeepLearningPreProcessModuleLogic().apply_rigid_registration(self.atlasNode, self.outputNode, self.update_rigid_progress)
        except Exception as e:
            # print(e)
            self.update_rigid_progress("Error: {0}".format(e))
            import traceback
            traceback.print_exc()
        finally:
            slicer.app.restoreOverrideCursor()


    # TODO remove
    # def click_flip_volume(self):
    #     logic = DeepLearningPreProcessModuleLogic()
    #     print("Flipping...")
    #
    #     vtkMatrix = vtk.vtkMatrix4x4()
    #     for row in range(4):
    #         for col in range(4):
    #             if row == col and row == 0:
    #                 vtkMatrix.SetElement(row, col, -1)
    #             elif row == col:
    #                 vtkMatrix.SetElement(row, col, 1)
    #             else:
    #                 vtkMatrix.SetElement(row, col, 0)
    #
    #     # Create MRML transform node
    #     self.transformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    #     self.transformNode.SetAndObserveMatrixTransformToParent(vtkMatrix)
    #
    #     self.inputNode.SetAndObserveTransformNodeID(self.transformNode.GetID())
    #     slicer.vtkSlicerTransformLogic().hardenTransform(self.inputNode)
    #
    #     self.resampleButton.enabled = True

    # def onApplyButton(self):
    # logic = DeepLearningTestLogic()
    # enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    # logic.run(self.inputSelector.currentNode())


# Main Logic
class DeepLearningPreProcessModuleLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

    @staticmethod
    def initialize_output_volume(input_node):
        output = slicer.vtkMRMLScalarVolumeNode()
        output.Copy(input_node)
        output.SetName("Output Volume")
        slicer.mrmlScene.AddNode(output)
        return output

    @staticmethod
    def initialize_fiducial_set(atlas_fiducial_node):
        fiducial_set = []
        for i in range(0, atlas_fiducial_node.GetNumberOfFiducials()):
            f = {'label': atlas_fiducial_node.GetNthFiducialLabel(i), 'table': None, 'input_indices': [0, 0, 0], 'atlas_indices': [0, 0, 0]}
            atlas_fiducial_node.GetNthFiducialPosition(i, f['atlas_indices'])
            fiducial_set.append(f)
        return fiducial_set

    @staticmethod
    def load_atlas_and_fiducials(side_indicator):
        framePath = slicer.os.path.dirname(slicer.os.path.abspath(inspect.getfile(inspect.currentframe()))) + "/Resources/Atlases/"
        atlasPath = framePath + 'Atlas_' + side_indicator + '.mha'
        fiducialPath = framePath + 'Fiducial_' + side_indicator + '.fcsv'
        atlasNode = slicer.util.loadVolume(atlasPath, returnNode=True)[1]
        atlasFiducialNode = slicer.util.loadMarkupsFiducialList(fiducialPath, returnNode=True)[1]
        atlasFiducialNode.SetName("Atlas Fiducials")
        atlasFiducialNode.SetLocked(True)
        return atlasNode, atlasFiducialNode

    @staticmethod
    def get_um_spacing(node):
        return [int(s*1000) for s in node]

    @staticmethod
    def resample_image(image, spacing):
        oldSpacing = [float("%.3f" % f) for f in image.GetSpacing()]
        oldSize = image.GetSize()
        newSize = [int(a * (b / c)) for a, b, c in zip(oldSize, oldSpacing, spacing)]
        resampler = sitk.ResampleImageFilter()
        # resampler.SetInterpolator(sitk.sitkBSpline)
        resampler.SetOutputDirection(image.GetDirection())
        resampler.SetOutputOrigin(image.GetOrigin())
        resampler.SetOutputSpacing(spacing)
        resampler.SetSize(newSize)
        resampledImage = resampler.Execute(image)
        return resampledImage

    @staticmethod
    def pull_node_resample_push(node, spacing_in_um):
        image = sitku.PullVolumeFromSlicer(node.GetID())
        resampledImage = DeepLearningPreProcessModuleLogic().resample_image(image, spacing_in_um)
        resampledNode = sitku.PushVolumeToSlicer(resampledImage, None, node.GetName() + "_Resampled", "vtkMRMLScalarVolumeNode")
        return resampledNode

    @staticmethod
    def apply_fiducial_registration(input_node, moving_node, atlas_fiducial_node, input_fiducial_node):
        # create temporary trimmed atlas fiducial set node (locked & hidden)
        trimmed_atlas_fiducial_node = slicer.vtkMRMLMarkupsFiducialNode()
        for i_f in range(0, input_fiducial_node.GetNumberOfFiducials()):
            for a_f in range(0, atlas_fiducial_node.GetNumberOfFiducials()):
                if input_fiducial_node.GetNthFiducialLabel(i_f) == atlas_fiducial_node.GetNthFiducialLabel(a_f):
                    pos = [0, 0, 0]
                    atlas_fiducial_node.GetNthFiducialPosition(a_f, pos)
                    trimmed_atlas_fiducial_node.AddFiducialFromArray(pos, atlas_fiducial_node.GetNthFiducialLabel(a_f))
                    break
        slicer.mrmlScene.AddNode(trimmed_atlas_fiducial_node)
        trimmed_atlas_fiducial_node.SetName("Trimmed Atlas Fiducials")
        trimmed_atlas_fiducial_node.SetLocked(True)
        for f in range(0, trimmed_atlas_fiducial_node.GetNumberOfFiducials()): trimmed_atlas_fiducial_node.SetNthFiducialVisibility(f, False)
        # start with fresh copy of input
        moving_node.Copy(input_node)
        moving_node.SetName("Output Volume")
        # process
        transform = slicer.vtkMRMLTransformNode()
        slicer.mrmlScene.AddNode(transform)
        output = slicer.cli.run(slicer.modules.fiducialregistration, None, wait_for_completion=True, parameters={
            'fixedLandmarks'   : trimmed_atlas_fiducial_node.GetID(),
            'movingLandmarks'  : input_fiducial_node.GetID(),
            'transformType'    : 'Rigid',
            "saveTransform"    : transform.GetID()
        })
        # apply
        moving_node.SetName(moving_node.GetName() + " +Fiducial-Transform")
        moving_node.ApplyTransform(transform.GetTransformToParent())
        # clean up
        slicer.mrmlScene.RemoveNode(transform)
        slicer.mrmlScene.RemoveNode(trimmed_atlas_fiducial_node)
        return output, moving_node

    @staticmethod
    def harden_fiducial_registration(fiducial_transformed_node):
        fiducial_transformed_node.HardenTransform()

    @staticmethod
    def apply_rigid_registration(atlas_node, moving_node, log_callback):
        logic = Elastix.ElastixLogic()
        logic.logStandardOutput = True
        logic.logCallback = log_callback
        logic.registerVolumes(
            fixedVolumeNode=atlas_node,
            movingVolumeNode=moving_node,
            parameterFilenames=logic.getRegistrationPresets()[1][5],
            outputVolumeNode=moving_node
        )
        moving_node.SetName(moving_node.GetName() + " +Rigid-Transform")
        return moving_node

    # TODO remove
    # def run_flip(self, volume):
    #     # Create VTK matrix object #Credit to Fernando
    #     vtkMatrix = vtk.vtkMatrix4x4()
    #     for row in range(4):
    #         for col in range(4):
    #             if row == col and row == 0:
    #                 vtkMatrix.SetElement(row, col, -1)
    #             elif row == col:
    #                 vtkMatrix.SetElement(row, col, 1)
    #             else:
    #                 vtkMatrix.SetElement(row, col, 0)
    #
    #     # Create MRML transform node
    #     self.transformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLinearTransformNode')
    #     self.transformNode.SetAndObserveMatrixTransformToParent(vtkMatrix)
    #
    #     volume.SetAndObserveTransformNodeID(self.transformNode.GetID())
    #     slicer.vtkSlicerTransformLogic().hardenTransform(volume)
    #
    # def has_image_data(self, volume_node):
    #     """This is an example logic method that
    # returns true if the passed in volume
    # node has valid image data
    # """
    #     if not volume_node:
    #         logging.debug('hasImageData failed: no volume node')
    #         return False
    #     if volume_node.GetImageData() is None:
    #         logging.debug('hasImageData failed: no image data in volume node')
    #         return False
    #     return True
    #
    # def is_valid_input_output_data(self, input_volume_node, output_volume_node):
    #     """Validates if the output is not the same as input
    # """
    #     if not input_volume_node:
    #         logging.debug('isValidInputOutputData failed: no input volume node defined')
    #         return False
    #     if input_volume_node.GetID() == output_volume_node.GetID():
    #         logging.debug(
    #             'isValidInputOutputData failed: input and output volume is the same. Create a new volume for output '
    #             'to avoid this error.'
    #         )
    #         return False
    #     return True
    #
    # def run(self, input_volume, output_volume, image_threshold, enable_screenshots=0):
    #     """
    # Run the actual algorithm
    # """
    #     return True


# Testing
class DeepLearningPreProcessModuleTest(ScriptedLoadableModuleTest):
    """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

    def setUp(self):
        """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        """Run as few or as many tests as needed here.
    """
        self.setUp()
        self.test_DeepLearningPreProcessModule1()

    def test_DeepLearningPreProcessModule1(self):
        """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

        self.delayDisplay("Starting the test")
        # #
        # # first, get some data
        # #
        # import SampleData
        # SampleData.downloadFromURL(
        #     nodeNames='FA',
        #     fileNames='FA.nrrd',
        #     uris='http://slicer.kitware.com/midas3/download?items=5767')
        # self.delayDisplay('Finished with download and loading')
        #
        # volumeNode = slicer.util.getNode(pattern="FA")
        # logic = DeepLearningPreProcessModuleLogic()
        # self.assertIsNotNone(logic.has_image_data(volumeNode))
        # self.delayDisplay('Test passed!')