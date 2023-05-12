"""
You can use this script for any commercial or non-commercial projects. You're not allowed to sell this script. 
Author - Petar3D
Initial Release Date - 10.05.2023
Version - 1.0

Description - Tool that allows you to build a temporary IK/FK setup on any rig, while preserving animation. Example - You select the controls for you arm FK chain (Shoulder, Elbow, Wrist), 
and then click the "FK to IK" button to apply an IK setup on top of your original FK controls. You can also isolate the code from the UI so you can put it into a marking menu or on the shelf.

"""

import maya.cmds as cmds
import maya.OpenMaya as om
from sys import exit


##################################################################################################################################################################################################################

def filterCurve_staticChannels(control):
#APPLIES A EULER FILTER AND REMOVES STATIC CHANNELS    
    refApplyKeyReducer = cmds.checkBoxGrp("ApplyKeyReducer_CheckBox", q=True, v1=True)
    refKeyReducerIntensity = cmds.floatFieldGrp("Intensity_FloatField", q=True, v1=True)
    refRemoveStaticChannels = cmds.checkBoxGrp("RemoveStaticChannels_CheckBox", q=True, v1=True)
    cmds.select(control)
    if refRemoveStaticChannels:
        cmds.delete(staticChannels=True, hi="none", cp=False, s=False)    
    cmds.select(control)
    cmds.filterCurve()
    if refApplyKeyReducer:
        cmds.filterCurve(f="keyReducer", pm=1, pre=refKeyReducerIntensity)

def lastKeyframeComparison(*keyframes):
#GATHERS THE LAST KEYFRAME OF EVERY ORIGINAL CONTROL AND COMPARES TO SEE WHICH ONE WAS THE FURTHEST IN THE TIMELINE
    lastKeyframe = max(*keyframes)
    return lastKeyframe
    
def lastKeyframeCut(lastKeyframe, *controls):
#FOR EVERY NEW CONTROL CREATED, WE CUT ITS TIMELINE UP TO WHERE THE LAST KEYFRAME OF THE PREVIOUS CONTROL WAS 
    timelineEnd = cmds.playbackOptions(max=True, q=True)
    for control in controls:
        if timelineEnd > lastKeyframe:
            cmds.cutKey(control, time=(lastKeyframe + 1, timelineEnd))

    
           
def hideAttributes(type, *controls):
#HIDES UNNECESSARY ATTRIBUTES ON THE CONTROLS        
    for item in controls:
        for attr in ["." + type + "X", "." + type + "Y", "." + type + "Z"]:
            cmds.setAttr(item + attr, k=False, cb=False)
            
def adjustControlSize(size, *controls):
#ADJUSTS THE SCALE OF THE CONTROLS, WHICH IN TURN RESETS THE SLIDER TO THE ORIGINAL VALUE
    for ctrl in controls:
        for attr in ["Shape.localScaleX", "Shape.localScaleY", "Shape.localScaleZ"]:
            cmds.setAttr(ctrl + attr, size)
            

def formLayout(name, topCoordinates, leftCoordinates):
#ADJUSTS THE POSITION OF THE UI FEATURES
    cmds.formLayout("formLayout", edit=True, attachForm=[(name, "top",topCoordinates), (name, "left",leftCoordinates)])    
                

def assistMessage(message, time):
#POPS UP A MESSAGE ON THE USER'S SCREEN TO INFORM THEM OF SOMETHING
    cmds.inViewMessage(amg=message, pos='midCenter', fade=True, fst=time, ck=True)
    exit()
    
def locatorSize(control):
    if cmds.currentUnit(q=True) == "m":
        for attr in [".scaleX", ".scaleY", ".scaleZ"]:
            cmds.setAttr(control + attr, 0.001)
            
def checkLocked(control):
#CHECK WHICH ATTRIBUTES ON THE CONTROL ARE LOCKED, SO AS TO KNOW WHICH ONES TO SKIP WHEN APPLYING CONSTRAINTS
        attributes = [".rotateX", ".rotateY", ".rotateZ"]
        lockedAttributes = []
        for attr in attributes:
            if cmds.getAttr(control + attr, lock=True):
                lockedAttributes.append(attr.lower()[-1:])
        return lockedAttributes
        
def constraint(parent, child, type, mo):
#CONSTRAINT SYSTEM
    lockedAttributes = checkLocked(child)
    if type == "parent":
        cmds.parentConstraint(parent, child, maintainOffset = mo, skipRotate = lockedAttributes)
    if type == "point":
        cmds.pointConstraint(parent, child, maintainOffset = mo, skip = lockedAttributes)
    if type == "orient":
        cmds.orientConstraint(parent, child, maintainOffset = mo, skip = lockedAttributes)           

##################################################################################################################################################################################################################
        
        
def fk_To_IK():
#CREATES A TEMPORARY IK SET-UP BY SELECTING EXISTING FK CONTROLS

    refPreserveAnimation = cmds.checkBoxGrp("PreserveAnimation_CheckBox", q=True, v1=True)
    refHideOriginalControls = cmds.checkBoxGrp("HideOriginalControls_CheckBox", q=True, v1=True)

    #SEPARATES THE SELECTED CONTROLS INTO THEIR OWN VARIABLES
    fk_CTRLS = cmds.ls(sl=True)
    if len(fk_CTRLS) != 3:
        assistMessage("<hl>Incorrect number of controls selected. To apply an IK setup, you need to select 3 FK controls, in order of parent to child.<hl>", 4000)
    parent_CTRL = fk_CTRLS[0]
    middle_CTRL = fk_CTRLS[1]
    child_CTRL = fk_CTRLS[2]
    cmds.select(cl=True)
    
    #QUERIES THE START AND END FRAME OF THE CURRENT TIMELINE
    timelineStart = cmds.playbackOptions(min=True, q=True)
    timelineEnd = cmds.playbackOptions(max=True, q=True)

    #CREATES TEMPORARY CONTROLS
    parent_temp_JNT = cmds.joint(n=parent_CTRL + "_temp_JNT")
    middle_temp_JNT = cmds.joint(n=middle_CTRL + "_temp_JNT")
    child_temp_JNT = cmds.joint(n=child_CTRL + "_temp_JNT")

    temp_IK_CTRL = cmds.spaceLocator(n=child_CTRL + "_temp_IK_CTRL")[0]
    locatorSize(temp_IK_CTRL)
    temp_PV = cmds.spaceLocator(n=middle_CTRL + "_temp_PV")[0]
    locatorSize(temp_PV)
    hideAttributes("rotate", temp_PV)
    hideAttributes("scale", temp_IK_CTRL, temp_PV)
    
    original_RO = cmds.getAttr(child_CTRL + ".rotateOrder")  #STORES THE ROTATION ORDER OF THE CURRENT CONTROL, TO BE ASSIGNED TO THE TEMP CONTROLS

    temp_IK_Contents = [parent_CTRL, middle_CTRL, child_CTRL, temp_IK_CTRL, temp_PV]
    temp_IK_Group = cmds.group(parent_temp_JNT, temp_IK_CTRL, temp_PV, n=parent_CTRL + "_temp_IK_Group")
    
    
    #CREATES EMPTY GROUPS AS PROXIES FOR REFERENCING THE ACTUAL CONTROLS LATER ON
    for obj in temp_IK_Contents:
        cmds.group(n=obj + "_temp_IK_Name", em=True, p=temp_IK_Group)


    def get_PoleVectorPosition(pos_Parent, pos_Middle, pos_Child):
        vector_parentJoint = om.MVector(pos_Parent[0], pos_Parent[1], pos_Parent[2])
        vector_middleJoint = om.MVector(pos_Middle[0], pos_Middle[1], pos_Middle[2])
        vector_childJoint = om.MVector(pos_Child[0], pos_Child[1], pos_Child[2])

        line = (vector_childJoint - vector_parentJoint) 
        point = (vector_middleJoint - vector_parentJoint)
        
        scale_value = (line * point) / (line * line)
        proj_vec = line * scale_value + vector_parentJoint
        
        parent_to_middle_len = (vector_middleJoint - vector_parentJoint).length()
        middle_to_child_len = (vector_childJoint - vector_middleJoint).length()
        total_length = parent_to_middle_len + middle_to_child_len
        
        position_poleVector = (vector_middleJoint - proj_vec).normal() * total_length + vector_middleJoint
        
        return position_poleVector

    #SNAPS THE TEMP CONTROLS TO THE POSITION OF THE ORIGINAL CONTROLS, BAKES THE ANIMATION DATA, THEN DELETES CONSTRAINTS
    def positionalSetup(parent, child):
        cmds.setAttr(child + ".rotateOrder", original_RO)
        cmds.matchTransform(child, parent, position=True, rotation=True)
        if "temp_PV" in child:
            position_parentJoint = cmds.xform(parent_temp_JNT, q=True, ws=True, t=True)
            position_middleJoint = cmds.xform(middle_temp_JNT, q=True, ws=True, t=True)
            position_childJoint = cmds.xform(child_temp_JNT, q=True, ws=True, t=True)
            position = get_PoleVectorPosition(position_parentJoint, position_middleJoint, position_childJoint)
            cmds.move(position.x, position.y, position.z, child)
        if "JNT" in child:
            cmds.makeIdentity(child, apply=True, t=True, r=True, s=True)
        lastKeyframe = cmds.findKeyframe(parent, which="last")
        constraint(parent, child, "parent", True)
        cmds.select(child)
        if refPreserveAnimation:
            cmds.bakeResults(t=(timelineStart, timelineEnd))                
        cmds.delete(cmds.listRelatives(type="constraint"))
        return lastKeyframe

    parentLastKeyframe = positionalSetup(parent_CTRL, parent_temp_JNT)
    middleLastKeyframe = positionalSetup(middle_CTRL, middle_temp_JNT)
    childLastKeyframe = positionalSetup(child_CTRL, child_temp_JNT)
    positionalSetup(child_temp_JNT, temp_IK_CTRL)
    positionalSetup(middle_temp_JNT, temp_PV)
    
    #CUTS THE TIMELINE UP TO WHERE THE LAST KEYFRAME WAS, FROM THE PREVIOUS CONTROLS
    lastKeyframe = lastKeyframeComparison(parentLastKeyframe, middleLastKeyframe, childLastKeyframe)
    lastKeyframeCut(lastKeyframe, temp_IK_CTRL, temp_PV)

    #REVERSE CONSTRAINT FROM THE TEMP CONTROLS TO THE ORIGINALS 
   
    constraint(parent_temp_JNT, parent_CTRL, "orient", True)
    constraint(middle_temp_JNT, middle_CTRL, "orient", True)
    constraint(child_temp_JNT, child_CTRL, "orient", True)
    
    constraint(parent_CTRL, parent_temp_JNT, "point", True)
    constraint(temp_IK_CTRL, child_temp_JNT, "orient", True)


    #SETS PREFERRED ANGLE ON THE TEMP JOINT CHAIN, AND APPLIES AN IK HANDLE ON IT
    cmds.joint(parent_temp_JNT, e=True, spa=True, ch=True)
    temp_IK_Handle = cmds.ikHandle(n=temp_IK_CTRL + "_ikHandle1", sj=parent_temp_JNT, ee=child_temp_JNT)[0]
    cmds.poleVectorConstraint(temp_PV, temp_IK_Handle)
    cmds.parent(temp_IK_Handle, temp_IK_CTRL, s=True)

    
    #CLEAN-UP
    objectsToHide = [parent_CTRL, middle_CTRL, child_CTRL]
    if refHideOriginalControls:
        cmds.hide(objectsToHide)
    cmds.setAttr(parent_temp_JNT + ".visibility", 0)
    cmds.setAttr(temp_IK_Handle + ".visibility", 0)
    filterCurve_staticChannels(temp_IK_CTRL)
    filterCurve_staticChannels(temp_PV)
    cmds.lockNode(temp_IK_Group)

    
    #LINK THE UI SLIDER TO THE LOCAL SCALE OF THE CONTROLS, SO THE USER CAN ADJUST THEM MANUALLY BASED ON THE RIG 
    refControlSize = cmds.floatSliderGrp("ControlSize_FloatSlider", q=True, v=True)
    cmds.connectControl("ControlSize_FloatSlider", temp_IK_CTRL + "Shape.localScaleX", temp_IK_CTRL + "Shape.localScaleY", temp_IK_CTRL + "Shape.localScaleZ",
    temp_PV + "Shape.localScaleX", temp_PV + "Shape.localScaleY", temp_PV + "Shape.localScaleZ")
    adjustControlSize(refControlSize, temp_IK_CTRL, temp_PV)
    
    cmds.select(temp_IK_CTRL)
    
        
#CREATES A TEMPORARY FK SET-UP BY SELECTING EXISTING IK CONTROLS
def ik_To_FK():
    refPreserveAnimation = cmds.checkBoxGrp("PreserveAnimation_CheckBox", q=True, v1=True)
    refHideOriginalControls = cmds.checkBoxGrp("HideOriginalControls_CheckBox", q=True, v1=True)
    
    #SEPARATES THE SELECTED CONTROLS INTO THEIR OWN VARIABLES
    ik_CTRLS = cmds.ls(sl=True)
    if len(ik_CTRLS) != 2:
        assistMessage("<hl>Incorrect number of controls selected. To apply an FK setup, you need to select the Pole Vector first and then the IK Control, in order.<hl>", 4000)
    poleVector = ik_CTRLS[0]
    ikControl = ik_CTRLS[1]
    

    #QUERIES THE START AND END FRAME OF THE CURRENT TIMELINE
    timelineStart = cmds.playbackOptions(min=True, q=True)
    timelineEnd = cmds.playbackOptions(max=True, q=True)
    cmds.currentTime(timelineStart, e=True)
    
    #FROM THE POLE VECTOR, WE DERIVE THE SELECTION OF THE PARENT AND MIDDLE JOINT THAT THE IK HANDLE INFLUENCES, AND STORE THEM IN VARIABLES
    cmds.select(poleVector, hi=True)
    poleVectorHierarchy = cmds.ls(sl=True)
    
    for obj in poleVectorHierarchy:
        poleVectorConstraint = cmds.listConnections(obj, type = "poleVectorConstraint")
        ikHandle = cmds.listConnections(poleVectorConstraint, type = "ikHandle")
        if ikHandle != None:
            break    
        else:
            assistMessage("<hl>Couldn't obtain IK handle from the rig. Selection order must be Pole Vector first, then IK control. Otherwise script may not work with this rig.<hl>", 4000)

    jointList = cmds.ikHandle(ikHandle, q=True, jl=True)
    parent_JNT = jointList[0]
    middle_JNT = jointList[1]
  
    
    #CREATE 3 TEMP LOCATORS, ADD A GROUP ON TOP OF THEM AND PARENT THEM TO EACH OTHER
    temp_FK_Group = cmds.group(em=True, n=parent_JNT + "_temp_FK_Group")
        
    temp_parent_FK_CTRL = cmds.spaceLocator(n=parent_JNT + "_temp_parent_FK_CTRL")[0]
    locatorSize(temp_parent_FK_CTRL)
    temp_parent_FK_CTRL_GRP = cmds.group(temp_parent_FK_CTRL, n=temp_parent_FK_CTRL + "_GRP")
    cmds.parent(temp_parent_FK_CTRL_GRP, temp_FK_Group)
    
    temp_middle_FK_CTRL = cmds.spaceLocator(n=middle_JNT + "_temp_middle_FK_CTRL")[0]
    locatorSize(temp_middle_FK_CTRL)
    temp_middle_FK_CTRL_GRP = cmds.group(temp_middle_FK_CTRL, n=temp_middle_FK_CTRL + "_GRP")
    cmds.parent(temp_middle_FK_CTRL_GRP, temp_parent_FK_CTRL)

    temp_child_FK_CTRL = cmds.spaceLocator(n=ikControl + "_temp_child_FK_CTRL")[0]
    locatorSize(temp_child_FK_CTRL)
    temp_child_FK_CTRL_GRP = cmds.group(temp_child_FK_CTRL, n=temp_child_FK_CTRL + "_GRP")
    cmds.parent(temp_child_FK_CTRL_GRP, temp_middle_FK_CTRL)
    
    temp_poleVector_CTRL = cmds.spaceLocator(n=poleVector + "_temp_poleVector_CTRL")[0]
    temp_poleVector_CTRL_GRP = cmds.group(temp_poleVector_CTRL, n=temp_poleVector_CTRL + "_GRP")
    cmds.parent(temp_poleVector_CTRL_GRP, temp_parent_FK_CTRL)
    
    temp_FK_Contents = [ikControl, poleVector, ikHandle[0], temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL, temp_poleVector_CTRL]
    
    
    #CREATES EMPTY GROUPS AS PROXIES FOR REFERENCING THE ACTUAL CONTROLS LATER ON
    for obj in temp_FK_Contents:
        cmds.group(n=obj + "_temp_FK_Name", em=True, p=temp_FK_Group)
        
    hideAttributes("translate", temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL)
    hideAttributes("scale", temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL)
    
    original_RO = cmds.getAttr(ikControl + ".rotateOrder")

    
    #SNAPS THE TEMP CONTROLS TO THE POSITION OF THE ORIGINAL CO NTROLS, BAKES THE ANIMATION DATA, THEN DELETES CONSTRAINTS
    def positionalSetup(parent, group, child):
        cmds.setAttr(child + ".rotateOrder", original_RO)
        cmds.matchTransform(group, parent, position=True, rotation=True)     
        constraint(parent, child, "parent", True) 
        cmds.select(child)
        lastKeyframe = cmds.findKeyframe(parent, which="last")
        if refPreserveAnimation:
            cmds.bakeResults(t=(timelineStart, timelineEnd))
        cmds.delete(cmds.listRelatives(type="constraint"))
        return lastKeyframe

    positionalSetup(parent_JNT, temp_parent_FK_CTRL_GRP, temp_parent_FK_CTRL)
    positionalSetup(middle_JNT, temp_middle_FK_CTRL_GRP, temp_middle_FK_CTRL)
    ikControlLastKeyframe = positionalSetup(ikControl, temp_child_FK_CTRL_GRP, temp_child_FK_CTRL)
    poleVectorLastKeyframe = positionalSetup(poleVector, temp_poleVector_CTRL_GRP, temp_poleVector_CTRL)

    #CUTS THE TIMELINE UP TO WHERE THE LAST KEYFRAME WAS, FROM THE PREVIOUS CONTROLS
    lastKeyframe = lastKeyframeComparison(ikControlLastKeyframe, poleVectorLastKeyframe)
    lastKeyframeCut(lastKeyframe, temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL)

    #REVERSE CONSTRAINT FROM THE TEMP CONTROLS TO THE ORIGINALS 
    constraint(temp_parent_FK_CTRL, parent_JNT, "orient", True)
    constraint(temp_middle_FK_CTRL, middle_JNT, "orient", True)
    constraint(temp_child_FK_CTRL, ikControl, "parent", True)
    
    constraint(parent_JNT, temp_parent_FK_CTRL, "point", True)
    constraint(temp_poleVector_CTRL, poleVector, "point", True)
    constraint(temp_parent_FK_CTRL, temp_poleVector_CTRL, "parent", True)

    
    #CLEAN-UP
    cmds.setAttr(ikHandle[0] + ".ikBlend", 0)
    objectsToHide = [poleVector, ikControl]
    if refHideOriginalControls:
        cmds.hide(objectsToHide)
    cmds.setAttr(temp_poleVector_CTRL + ".visibility", 0)
    cmds.lockNode(temp_FK_Group)
    
    filterCurve_staticChannels(temp_parent_FK_CTRL)
    filterCurve_staticChannels(temp_middle_FK_CTRL)
    filterCurve_staticChannels(temp_child_FK_CTRL)
    
    
    #LINK THE UI SLIDER TO THE LOCAL SCALE OF THE CONTROLS, SO THE USER CAN ADJUST THEM MANUALLY BASED ON THE RIG 
    refControlSize = cmds.floatSliderGrp("ControlSize_FloatSlider", q=True, v=True)
    cmds.connectControl("ControlSize_FloatSlider", temp_parent_FK_CTRL + "Shape.localScaleX", temp_parent_FK_CTRL + "Shape.localScaleY", temp_parent_FK_CTRL + "Shape.localScaleZ",
    temp_middle_FK_CTRL + "Shape.localScaleX", temp_middle_FK_CTRL + "Shape.localScaleY", temp_middle_FK_CTRL + "Shape.localScaleZ",
    temp_child_FK_CTRL + "Shape.localScaleX", temp_child_FK_CTRL + "Shape.localScaleY", temp_child_FK_CTRL + "Shape.localScaleZ")
    adjustControlSize(refControlSize, temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL)
    
    cmds.select(temp_parent_FK_CTRL)
    
    
def deleteSetup():
#RESTORES THE PREVIOUS SET-UP 
   
    refPreserveAnimation = cmds.checkBoxGrp("PreserveAnimation_CheckBox", q=True, v1=True)
    refHideOriginalControls = cmds.checkBoxGrp("HideOriginalControls_CheckBox", q=True, v1=True)
    
    #QUERIES THE START AND END FRAME OF THE CURRENT TIMELINE
    timelineStart = cmds.playbackOptions(min=True, q=True)
    timelineEnd = cmds.playbackOptions(max=True, q=True)
    
    #BAKES THE PREVIOUS CONTROLS, CLEANS UP THE CURVES, DELETES CURRENT CONTROLS AND BRINGS BACK ORIGINALS
    def cleanUp():
        control = group_Contents[i][:-13]
        cmds.select(control)
        if refPreserveAnimation:
            cmds.bakeResults(t = (timelineStart, timelineEnd))
            lastKeyframeCut(lastKeyframe, control)
        cmds.showHidden(control)
                    
        filterCurve_staticChannels(control)
    
    temp_Selection = cmds.ls(sl=True)
    if len(temp_Selection) == 0:
        assistMessage("<hl>To delete a temporary setup, you have to select one of its controls.<hl>", 2500)
        
    if "FK_CTRL" in temp_Selection[0] or "temp_IK_CTRL" in temp_Selection[0] or "temp_PV" in temp_Selection[0]:
        for i in range(6):
            cmds.pickWalk(d="up")
        temp_Group = cmds.ls(sl=True)[0]
        if "temp_IK_Group" in temp_Group or "temp_FK_Group" in temp_Group:
            group_Contents = cmds.listRelatives(temp_Group)
                
            if "temp_IK_Group" in temp_Group:
                ikControlLastKeyframe = cmds.findKeyframe(group_Contents[6][:-13], which="last")
                poleVectorLastKeyframe = cmds.findKeyframe(group_Contents[7][:-13], which="last")
                
                lastKeyframe = lastKeyframeComparison(ikControlLastKeyframe, poleVectorLastKeyframe)
                for i in range(3,6):
                    cleanUp()
                    
            elif "temp_FK_Group" in temp_Group:
                parentLastKeyframe = cmds.findKeyframe(group_Contents[4][:-13], which="last")
                middleLastKeyframe = cmds.findKeyframe(group_Contents[5][:-13], which="last")
                childLastKeyframe = cmds.findKeyframe(group_Contents[6][:-13], which="last")

                lastKeyframe = lastKeyframeComparison(parentLastKeyframe, middleLastKeyframe, childLastKeyframe)
                for i in range(1,3):
                    cleanUp()
                cmds.setAttr(group_Contents[3][:-13] + ".ikBlend", 1)
                
            cmds.connectControl("ControlSize_FloatSlider", "")
            cmds.lockNode(temp_Group, l=False)
            cmds.delete(temp_Group)  
    else:
        assistMessage("<hl>Incorrect selection. To delete a temporary IK or FK setup, select one of its controls and then click the button.<hl>", 4500)
    

def generateCode():
#YOU SELECT ONE OF THREE OPTIONS FOR WHAT CODE YOU WANT TO ISOLATE FROM THE SCRIPT: FK TO IK, IK TO FK, DELETE SETUP. 
    
    cmds.scrollField("GenerateCodeOutputWindow", e=True, cl=True)
    
#THIS FIRST BLOCK OF CODE GETS GENERATED FOR ALL
    code = """
import maya.cmds as cmds
import maya.OpenMaya as om
from sys import exit

refRemoveStaticChannels = """ + str(cmds.checkBoxGrp("RemoveStaticChannels_CheckBox", q=True, v1=True)) + """
refApplyKeyReducer = """ + str(cmds.checkBoxGrp("ApplyKeyReducer_CheckBox", q=True, v1=True)) + """
refKeyReducerIntensity = """ + str(cmds.floatFieldGrp("Intensity_FloatField", q=True, v1=True)) + """

def filterCurve_staticChannels(control):
    cmds.select(control)
    if refRemoveStaticChannels:
        cmds.delete(staticChannels=True, hi="none", cp=False, s=False)    
    cmds.select(control)
    cmds.selectKey(cl=True)
    cmds.selectKey()
    cmds.filterCurve()
    if refApplyKeyReducer:
            cmds.filterCurve(f="keyReducer", pm=1, pre=refKeyReducerIntensity)
            

#GATHERS THE LAST KEYFRAME OF EVERY ORIGINAL CONTROL AND COMPARES TO SEE WHICH ONE WAS THE FURTHEST IN THE TIMELINE
def lastKeyframeComparison(*keyframes):
    lastKeyframe = max(*keyframes)
    return lastKeyframe
    
#FOR EVERY NEW CONTROL CREATED, WE CUT ITS TIMELINE UP TO WHERE THE LAST KEYFRAME OF THE PREVIOUS CONTROL WAS 
def lastKeyframeCut(lastKeyframe, *controls):
    timelineEnd = cmds.playbackOptions(max=True, q=True)
    for control in controls:
        if timelineEnd > lastKeyframe:
            cmds.cutKey(control, time=(lastKeyframe + 1, timelineEnd))
            
            
#HIDES UNNECESSARY ATTRIBUTES ON THE CONTROLS    
def hideAttributes(type, *controls):
    for item in controls:
        for attr in ["." + type + "X", "." + type + "Y", "." + type + "Z"]:
            cmds.setAttr(item + attr, k=False, cb=False)
            
def assistMessage(message, time):
    cmds.inViewMessage(amg=message, pos='midCenter', fade=True, fst=time, ck=True)
    exit()

def locatorSize(control):
    if cmds.currentUnit(q=True) == "m":
        for attr in [".scaleX", ".scaleY", ".scaleZ"]:
            cmds.setAttr(control + attr, 0.001)
            
#CHECK WHICH ATTRIBUTES ON THE CONTROL ARE LOCKED, SO AS TO KNOW WHICH ONES TO SKIP WHEN APPLYING CONSTRAINTS            
def checkLocked(control):
        attributes = [".rotateX", ".rotateY", ".rotateZ"]
        lockedAttributes = []
        for attr in attributes:
            if cmds.getAttr(control + attr, lock=True):
                lockedAttributes.append(attr.lower()[-1:])
        return lockedAttributes
        
def constraint(parent, child, type, mo):
#CONSTRAINT SYSTEM
    lockedAttributes = checkLocked(child)
    if type == "parent":
        cmds.parentConstraint(parent, child, maintainOffset = mo, skipRotate = lockedAttributes)
    if type == "point":
        cmds.pointConstraint(parent, child, maintainOffset = mo, skip = lockedAttributes)
    if type == "orient":
        cmds.orientConstraint(parent, child, maintainOffset = mo, skip = lockedAttributes)   

""" 

#GENERATES THE CODE FOR APPLYING THE IK SETUP
    if cmds.radioButtonGrp("GenerateCodeOptions_RadioB", q=True, select=True) == 1:
            
        code += """
refPreserveAnimation = """ + str(cmds.checkBoxGrp("PreserveAnimation_CheckBox", q=True, v1=True)) + """
refHideOriginalControls = """ + str(cmds.checkBoxGrp("HideOriginalControls_CheckBox", q=True, v1=True)) + """
refControlSize = """ + str(cmds.floatSliderGrp("ControlSize_FloatSlider", q=True, v=True))
            
        if len(cmds.ls(sl=True)) == 3:
            fk_CTRLS = cmds.ls(sl=True)
            code += """
parent_CTRL = """  "\"" +  fk_CTRLS[0] + "\"" """
middle_CTRL = """ "\"" +  fk_CTRLS[1] + "\"" """
child_CTRL = """ "\"" +  fk_CTRLS[2] + "\"" """
if cmds.objExists(child_CTRL + "_temp_IK_CTRL"):
    assistMessage("<hl>This setup already exists.<hl>", 5000)
cmds.select(cl=True)
"""
                
        elif len(cmds.ls(sl=True)) == 0:
            code += """
fk_CTRLS = cmds.ls(sl=True)
if len(fk_CTRLS) != 3:
    assistMessage("<hl>Incorrect number of controls selected. To apply an IK setup, you need to select 3 FK controls, in order of parent to child.<hl>", 5000)
parent_CTRL = fk_CTRLS[0]
middle_CTRL = fk_CTRLS[1]
child_CTRL = fk_CTRLS[2]
cmds.select(cl=True)
"""
        else:
            assistMessage("<hl>Incorrect number of controls selected. For a specific IK setup, select 3 FK controls. For a generic setup, have no selections.<hl>", 5000)
                
        code +="""
#QUERIES THE START AND END FRAME OF THE CURRENT TIMELINE
timelineStart = cmds.playbackOptions(min=True, q=True)
timelineEnd = cmds.playbackOptions(max=True, q=True)


#CREATES TEMPORARY CONTROLS
parent_temp_JNT = cmds.joint(n=parent_CTRL + "_temp_JNT")
middle_temp_JNT = cmds.joint(n=middle_CTRL + "_temp_JNT")
child_temp_JNT = cmds.joint(n=child_CTRL + "_temp_JNT")

temp_IK_CTRL = cmds.spaceLocator(n=child_CTRL + "_temp_IK_CTRL")[0]
locatorSize(temp_IK_CTRL)
temp_PV = cmds.spaceLocator(n=middle_CTRL + "_temp_PV")[0]
locatorSize(temp_PV)
hideAttributes("rotate", temp_PV)
hideAttributes("scale", temp_IK_CTRL, temp_PV)

original_RO = cmds.getAttr(child_CTRL + ".rotateOrder")


temp_IK_Contents = [parent_CTRL, middle_CTRL, child_CTRL, temp_IK_CTRL, temp_PV]
temp_IK_Group = cmds.group(parent_temp_JNT, temp_IK_CTRL, temp_PV, n=parent_CTRL + "_temp_IK_Group")


#CREATES EMPTY GROUPS AS PROXIES FOR REFERENCING THE ACTUAL CONTROLS LATER ON
for obj in temp_IK_Contents:
    cmds.group(n=obj + "_temp_IK_Name", em=True, p=temp_IK_Group)
   

def get_PoleVectorPosition(pos_Parent, pos_Middle, pos_Child):
    vector_parentJoint = om.MVector(pos_Parent[0], pos_Parent[1], pos_Parent[2])
    vector_middleJoint = om.MVector(pos_Middle[0], pos_Middle[1], pos_Middle[2])
    vector_childJoint = om.MVector(pos_Child[0], pos_Child[1], pos_Child[2])

    line = (vector_childJoint - vector_parentJoint) 
    point = (vector_middleJoint - vector_parentJoint)
    
    scale_value = (line * point) / (line * line)
    proj_vec = line * scale_value + vector_parentJoint
    
    parent_to_middle_len = (vector_middleJoint - vector_parentJoint).length()
    middle_to_child_len = (vector_childJoint - vector_middleJoint).length()
    total_length = parent_to_middle_len + middle_to_child_len
    
    position_poleVector = (vector_middleJoint - proj_vec).normal() * total_length + vector_middleJoint
    
    return position_poleVector


#SNAPS THE TEMP CONTROLS TO THE POSITION OF THE ORIGINAL CONTROLS, BAKES THE ANIMATION DATA, THEN DELETES CONSTRAINTS
def positionalSetup(parent, child):
    cmds.setAttr(child + ".rotateOrder", original_RO)
    cmds.matchTransform(child, parent, position=True, rotation=True)
    if "temp_PV" in child:
        position_parentJoint = cmds.xform(parent_temp_JNT, q=True, ws=True, t=True)
        position_middleJoint = cmds.xform(middle_temp_JNT, q=True, ws=True, t=True)
        position_childJoint = cmds.xform(child_temp_JNT, q=True, ws=True, t=True)
        position = get_PoleVectorPosition(position_parentJoint, position_middleJoint, position_childJoint)
        cmds.move(position.x, position.y, position.z, child)
    if "JNT" in child:
        cmds.makeIdentity(child, apply=True, t=True, r=True, s=True)
    lastKeyframe = cmds.findKeyframe(parent, which="last")
    constraint(parent, child, "parent", True)
    cmds.select(child)
    if refPreserveAnimation:
        cmds.bakeResults(t=(timelineStart, timelineEnd))                
    cmds.delete(cmds.listRelatives(type="constraint"))
    return lastKeyframe

parentLastKeyframe = positionalSetup(parent_CTRL, parent_temp_JNT)
middleLastKeyframe = positionalSetup(middle_CTRL, middle_temp_JNT)
childLastKeyframe = positionalSetup(child_CTRL, child_temp_JNT)

positionalSetup(child_temp_JNT, temp_IK_CTRL)
positionalSetup(middle_temp_JNT, temp_PV)

#CUTS THE TIMELINE UP TO WHERE THE LAST KEYFRAME WAS, FROM THE PREVIOUS CONTROLS
lastKeyframe = lastKeyframeComparison(parentLastKeyframe, middleLastKeyframe, childLastKeyframe)
lastKeyframeCut(lastKeyframe, temp_IK_CTRL, temp_PV)


#REVERSE CONSTRAINT FROM THE TEMP CONTROLS TO THE ORIGINALS 
constraint(parent_temp_JNT, parent_CTRL, "orient", True)
constraint(middle_temp_JNT, middle_CTRL, "orient", True)
constraint(child_temp_JNT, child_CTRL, "orient", True)

constraint(parent_CTRL, parent_temp_JNT, "point", True)
constraint(temp_IK_CTRL, child_temp_JNT, "orient", True)


#SETS PREFERRED ANGLE ON THE TEMP JOINT CHAIN, AND APPLIES AN IK HANDLE ON IT
cmds.joint(parent_temp_JNT, e=True, spa=True, ch=True)
temp_IK_Handle = cmds.ikHandle(n=temp_IK_CTRL + "_ikHandle1", sj=parent_temp_JNT, ee=child_temp_JNT)[0]
cmds.poleVectorConstraint(temp_PV, temp_IK_Handle)
cmds.parent(temp_IK_Handle, temp_IK_CTRL, s=True)


#CLEAN-UP
objectsToHide = [parent_CTRL, middle_CTRL, child_CTRL]
if refHideOriginalControls:
    cmds.hide(objectsToHide)
cmds.setAttr(parent_temp_JNT + ".visibility", 0)
cmds.setAttr(temp_IK_Handle + ".visibility", 0)

filterCurve_staticChannels(temp_IK_CTRL)
filterCurve_staticChannels(temp_PV)

ik_Setup_Controls = [temp_IK_CTRL, temp_PV]

for ctrl in ik_Setup_Controls:
    for attr in ["Shape.localScaleX", "Shape.localScaleY", "Shape.localScaleZ"]:
        cmds.setAttr(ctrl + attr, refControlSize)

cmds.select(temp_IK_CTRL)"""
    

#GENERATES THE CODE FOR APPLYING THE FK SETUP
    elif cmds.radioButtonGrp("GenerateCodeOptions_RadioB", q=True, select=True) == 2:
        
        code +="""    
refPreserveAnimation = """ + str(cmds.checkBoxGrp("PreserveAnimation_CheckBox", q=True, v1=True)) + """
refHideOriginalControls = """ + str(cmds.checkBoxGrp("HideOriginalControls_CheckBox", q=True, v1=True)) + """
refControlSize = """ + str(cmds.floatSliderGrp("ControlSize_FloatSlider", q=True, v=True))

        if len(cmds.ls(sl=True)) == 2:
            ik_CTRLS = cmds.ls(sl=True)
            code +="""
poleVector = """ "\"" +  ik_CTRLS[0] + "\"" """
ikControl = """ "\"" +  ik_CTRLS[1] + "\"" """
if cmds.objExists(ikControl + "_temp_child_FK_CTRL"):
    assistMessage("<hl>This setup already exists.<hl>", 5000)
"""
            
        elif len(cmds.ls(sl=True)) == 0:
            code +="""
ik_CTRLS = cmds.ls(sl=True)
if len(ik_CTRLS) != 2:
    assistMessage("<hl>Incorrect number of controls selected. To apply an FK setup, you need to select the Pole Vector first and then the IK Control, in order.<hl>", 5000)
poleVector = ik_CTRLS[0]
ikControl = ik_CTRLS[1]
"""
        else:
            assistMessage("<hl>Incorrect number of controls selected. For a specific FK setup, select the Pole Vector and IK Control in order. For a generic setup, have no selections.<hl>", 5000)
                
        code +="""
#QUERIES THE START AND END FRAME OF THE CURRENT TIMELINE
timelineStart = cmds.playbackOptions(min=True, q=True)
timelineEnd = cmds.playbackOptions(max=True, q=True)


cmds.currentTime(timelineStart, e=True)

#FROM THE POLE VECTOR, WE DERIVE THE SELECTION OF THE PARENT AND MIDDLE JOINT THAT THE IK HANDLE INFLUENCES, AND STORE THEM IN VARIABLES
cmds.select(poleVector, hi=True)
poleVectorHierarchy = cmds.ls(sl=True)

for obj in poleVectorHierarchy:
    poleVectorConstraint = cmds.listConnections(obj, type = "poleVectorConstraint")
    ikHandle = cmds.listConnections(poleVectorConstraint, type = "ikHandle")
    if ikHandle != None:
        break     
    else:
        assistMessage("<hl>Couldn't obtain IK handle from the rig. Selection order must be Pole Vector first, then IK control. Otherwise script may not work with this rig.<hl>", 4000)       

jointList = cmds.ikHandle(ikHandle, q=True, jl=True)
parent_JNT = jointList[0]
middle_JNT = jointList[1]


#CREATE 3 TEMP LOCATORS, ADD A GROUP ON TOP OF THEM AND PARENT THEM TO EACH OTHER
temp_FK_Group = cmds.group(em=True, n=parent_JNT + "_temp_FK_Group")
    
temp_parent_FK_CTRL = cmds.spaceLocator(n=parent_JNT + "_temp_parent_FK_CTRL")[0]
locatorSize(temp_parent_FK_CTRL)
temp_parent_FK_CTRL_GRP = cmds.group(temp_parent_FK_CTRL, n=temp_parent_FK_CTRL + "_GRP")
cmds.parent(temp_parent_FK_CTRL_GRP, temp_FK_Group)

temp_middle_FK_CTRL = cmds.spaceLocator(n=middle_JNT + "_temp_middle_FK_CTRL")[0]
locatorSize(temp_middle_FK_CTRL)
temp_middle_FK_CTRL_GRP = cmds.group(temp_middle_FK_CTRL, n=temp_middle_FK_CTRL + "_GRP")
cmds.parent(temp_middle_FK_CTRL_GRP, temp_parent_FK_CTRL)

temp_child_FK_CTRL = cmds.spaceLocator(n=ikControl + "_temp_child_FK_CTRL")[0]
locatorSize(temp_child_FK_CTRL)
temp_child_FK_CTRL_GRP = cmds.group(temp_child_FK_CTRL, n=temp_child_FK_CTRL + "_GRP")
cmds.parent(temp_child_FK_CTRL_GRP, temp_middle_FK_CTRL)

temp_poleVector_CTRL = cmds.spaceLocator(n=poleVector + "_temp_poleVector_CTRL")[0]
temp_poleVector_CTRL_GRP = cmds.group(temp_poleVector_CTRL, n=temp_poleVector_CTRL + "_GRP")
cmds.parent(temp_poleVector_CTRL_GRP, temp_parent_FK_CTRL)

temp_FK_Contents = [ikControl, poleVector, ikHandle[0], temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL, temp_poleVector_CTRL]



#CREATES EMPTY GROUPS AS PROXIES FOR REFERENCING THE ACTUAL CONTROLS LATER ON
for obj in temp_FK_Contents:
    cmds.group(n=obj + "_temp_FK_Name", em=True, p=temp_FK_Group)

hideAttributes("translate", temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL)
hideAttributes("scale", temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL)

original_RO = cmds.getAttr(ikControl + ".rotateOrder")



#SNAPS THE TEMP CONTROLS TO THE POSITION OF THE ORIGINAL CO NTROLS, BAKES THE ANIMATION DATA, THEN DELETES CONSTRAINTS
def positionalSetup(parent, group, child):
    cmds.setAttr(child + ".rotateOrder", original_RO)
    cmds.matchTransform(group, parent, position=True, rotation=True)     
    constraint(parent, child, "parent", True) 
    cmds.select(child)
    lastKeyframe = cmds.findKeyframe(parent, which="last")
    if refPreserveAnimation:
        cmds.bakeResults(t=(timelineStart, timelineEnd))
    cmds.delete(cmds.listRelatives(type="constraint"))
    return lastKeyframe

positionalSetup(parent_JNT, temp_parent_FK_CTRL_GRP, temp_parent_FK_CTRL)
positionalSetup(middle_JNT, temp_middle_FK_CTRL_GRP, temp_middle_FK_CTRL)
ikControlLastKeyframe = positionalSetup(ikControl, temp_child_FK_CTRL_GRP, temp_child_FK_CTRL)
poleVectorLastKeyframe = positionalSetup(poleVector, temp_poleVector_CTRL_GRP, temp_poleVector_CTRL)

#CUTS THE TIMELINE UP TO WHERE THE LAST KEYFRAME WAS, FROM THE PREVIOUS CONTROLS
lastKeyframe = lastKeyframeComparison(ikControlLastKeyframe, poleVectorLastKeyframe)
lastKeyframeCut(lastKeyframe, temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL)

#REVERSE CONSTRAINT FROM THE TEMP CONTROLS TO THE ORIGINALS 
constraint(temp_parent_FK_CTRL, parent_JNT, "orient", True)
constraint(temp_middle_FK_CTRL, middle_JNT, "orient", True)
constraint(temp_child_FK_CTRL, ikControl, "parent", True)

constraint(parent_JNT, temp_parent_FK_CTRL, "point", True)
constraint(temp_poleVector_CTRL, poleVector, "point", True)
constraint(temp_parent_FK_CTRL, temp_poleVector_CTRL, "parent", True)


#CLEAN-UP
cmds.setAttr(ikHandle[0] + ".ikBlend", 0)
objectsToHide = [poleVector, ikControl]
if refHideOriginalControls:
    cmds.hide(objectsToHide)
cmds.setAttr(temp_poleVector_CTRL + ".visibility", 0)

filterCurve_staticChannels(temp_parent_FK_CTRL)
filterCurve_staticChannels(temp_middle_FK_CTRL)
filterCurve_staticChannels(temp_child_FK_CTRL)

ik_Setup_Controls = [temp_parent_FK_CTRL, temp_middle_FK_CTRL, temp_child_FK_CTRL]

for ctrl in ik_Setup_Controls:
    for attr in ["Shape.localScaleX", "Shape.localScaleY", "Shape.localScaleZ"]:
        cmds.setAttr(ctrl + attr, refControlSize)

cmds.select(temp_parent_FK_CTRL)
"""

#GENERATES THE CODE FOR DELETING THE SETUP
    elif cmds.radioButtonGrp("GenerateCodeOptions_RadioB", q=True, select=True) == 3:
        
        code += """
refPreserveAnimation = """ + str(cmds.checkBoxGrp("PreserveAnimation_CheckBox", q=True, v1=True)) + """
refHideOriginalControls = """ + str(cmds.checkBoxGrp("HideOriginalControls_CheckBox", q=True, v1=True)) + """

#QUERIES THE START AND END FRAME OF THE CURRENT TIMELINE
timelineStart = cmds.playbackOptions(min=True, q=True)
timelineEnd = cmds.playbackOptions(max=True, q=True)

#BAKES THE PREVIOUS CONTROLS, CLEANS UP THE CURVES, DELETES CURRENT CONTROLS AND BRINGS BACK ORIGINALS
def cleanUp():
    control = group_Contents[i][:-13]
    cmds.select(control)
    if refPreserveAnimation:
        cmds.bakeResults(t = (timelineStart, timelineEnd))
        lastKeyframeCut(lastKeyframe, control)
    cmds.showHidden(control)
                
    filterCurve_staticChannels(control)"""
    
        temp_Selection = cmds.ls(sl=True)
        if len(temp_Selection) > 0:
            if "FK_CTRL" in temp_Selection[0] or "temp_IK_CTRL" in temp_Selection[0] or "temp_PV" in temp_Selection[0]:
                for i in range(6):
                    cmds.pickWalk(d="up")
            else:
                assistMessage("<hl>Incorrect selection. To generate the code for deleting an IK or FK setup, select one of its controls and then click the button.<hl>", 4500)
            code+="""  
temp_Group = """ "\"" + cmds.ls(sl=True)[0] + "\"" """
if cmds.objExists(temp_Group) == False:
    assistMessage("<hl>There's no setup to be deleted.<hl>", 5000)"""
        
        elif len(temp_Selection) == 0:
            code+="""
temp_Selection = cmds.ls(sl=True)
if len(temp_Selection) == 0:
        assistMessage("<hl>To delete a temporary setup, you have to select one of its controls.<hl>", 4500)
if "FK_CTRL" in temp_Selection[0] or "temp_IK_CTRL" in temp_Selection[0] or "temp_PV" in temp_Selection[0]:
    for i in range(6):
        cmds.pickWalk(d="up")
else:
    assistMessage("<hl>Incorrect selection. To delete a temporary IK or FK setup, select one of its controls and then execute.<hl>", 4500)

temp_Group = cmds.ls(sl=True)[0] """    

        code +="""
group_Contents = cmds.listRelatives(temp_Group)
        
if "temp_IK_Group" in temp_Group:
    ikControlLastKeyframe = cmds.findKeyframe(group_Contents[6][:-13], which="last")
    poleVectorLastKeyframe = cmds.findKeyframe(group_Contents[7][:-13], which="last")
    
    lastKeyframe = lastKeyframeComparison(ikControlLastKeyframe, poleVectorLastKeyframe)
    for i in range(3,6):
        cleanUp()
        

elif "temp_FK_Group" in temp_Group:
    parentLastKeyframe = cmds.findKeyframe(group_Contents[4][:-13], which="last")
    middleLastKeyframe = cmds.findKeyframe(group_Contents[5][:-13], which="last")
    childLastKeyframe = cmds.findKeyframe(group_Contents[6][:-13], which="last")

    lastKeyframe = lastKeyframeComparison(parentLastKeyframe, middleLastKeyframe, childLastKeyframe)
    for i in range(1,3):
        cleanUp()
    cmds.setAttr(group_Contents[3][:-13] + ".ikBlend", 1)

cmds.lockNode(temp_Group, l=False)
cmds.delete(temp_Group)     


"""
            
    cmds.scrollField("GenerateCodeOutputWindow", e=True, tx=code)

#UI LOGIC
def userInterface():
    if cmds.window("IK_FK_Switcher", ex=True):
        cmds.deleteUI("IK_FK_Switcher")
        

    cmds.window("IK_FK_Switcher", title="IK/FK Switcher, by Petar3D", wh=[360, 242], s=False)
    cmds.formLayout("formLayout", numberOfDivisions=100, w=360, h=242)


    cmds.button("fkToIK_Button", l="FK to IK", recomputeSize = True, bgc=[0.6220035095750363, 0.8836957351033798, 1.0], h = 43, w = 100,  parent ="formLayout", command="fk_To_IK()", 
    ann="Applies a temporary IK setup on top of your existing FK chain.\nHow to use:  Select 3 FK controls, starting from the parent to the child, then click this button.")
    formLayout("fkToIK_Button", 11, 16)
    cmds.button("ikToFK_Button", l="IK to FK ", recomputeSize = True, bgc=[1.0, 1.0, 0.6220035095750363], h = 43, w = 100,  parent ="formLayout", command="ik_To_FK()",
    ann="Applies a temporary FK setup on top of your existing IK chain.\nHow to use:  Select the pole vector and then the IK control, then click this button.")
    formLayout("ikToFK_Button", 11, 131)
    cmds.button("DeleteSetup_Button", l="Delete Setup", recomputeSize = True, bgc=[1.0, 0.6220035095750363, 0.6220035095750363], h = 43, w = 99,  parent ="formLayout", command="deleteSetup()",
    ann="Deletes the temporary IK/FK setups and brings back the original.\nHow to use:  Select a control from the current setup, then click this button.")
    formLayout("DeleteSetup_Button", 11, 246)
    cmds.button("ExtraOptions_Button", l="Extra Options", recomputeSize = True, bgc=[0.6220035095750363, 1.0, 0.6656137941557946], h = 34, w = 90,  parent ="formLayout", command = "extraOptions()")
    formLayout("ExtraOptions_Button", 200, 262)
    cmds.textFieldGrp("Settings_Button", l="Settings", bgc=[0.4429541466392004, 0.4429541466392004, 0.4429541466392004], cw=(1,91),h = 23, w = 145,  parent ="formLayout", ed=False)
    formLayout("Settings_Button", 75, 16)

    cmds.checkBoxGrp("PreserveAnimation_CheckBox", l="Preserve Animation: ", ncb=1, l1="", cw = (1, 104), w = 125, vr=False, v1=True,  parent ="formLayout",
    ann="When you apply a temp setup or delete the current one, it bakes and preserves the animation changes.")
    formLayout("PreserveAnimation_CheckBox", 199, 14)
    cmds.checkBoxGrp("ApplyKeyReducer_CheckBox", l="Apply Key Reducer: ", ncb=1, l1="", cw = (1, 100), w = 151, vr=False,  parent ="formLayout",
    ann="When the animation bakes across, this feature reduces the amount of keyframes on your curves.")
    formLayout("ApplyKeyReducer_CheckBox", 128, 14)
    cmds.checkBoxGrp("RemoveStaticChannels_CheckBox", l="Remove Static Channels: ", ncb=1, l1="", cw = (1, 128), w = 166, vr=False,  parent ="formLayout",
    ann="When ticked on, after the bake, static channels get removed.\nStatic channels are curves like scaleX/Y/Z that get baked but have no changes to them across the timeline, so they're redundant and take up space.")
    formLayout("RemoveStaticChannels_CheckBox", 151, 14)
    cmds.checkBoxGrp("HideOriginalControls_CheckBox", l="Hide Original Controls: ", ncb=1, l1="", cw = (1, 122), w = 171, vr=False, v1=True,  parent ="formLayout",
    ann="When applying your temporary setup, this hides the original controls, for more clarity")
    formLayout("HideOriginalControls_CheckBox", 175, 14)

    cmds.floatFieldGrp("Intensity_FloatField", l="Intensity: ", numberOfFields=1, v1=1.0,  cw = (1, 52), w = 137, parent ="formLayout",
    ann="The higher the amount, the less keyframes you'll have when applying the key reducer,\nbut you lose out on how precisely the animation gets baked across.")
    formLayout("Intensity_FloatField", 125, 139)

    cmds.floatSliderGrp("ControlSize_FloatSlider", l="Control Scale: ", field=True, minValue=1, maxValue=50, v=15, cw = (1, 74), w = 348, parent ="formLayout",
    ann="Once you create a temporary setup, use this slider to adjust the size of the controls that get created, if they appear too big or too small.")
    formLayout("ControlSize_FloatSlider", 103, 14)

    cmds.separator("Proxy_HRSeparator", hr=True,bgc=[0.6569924467841611, 0.6569924467841611, 0.6569924467841611], style="none", h = 3, w = 394)
    formLayout("Proxy_HRSeparator", 63, -8)

    cmds.showWindow("IK_FK_Switcher")
    

def extraOptions():
    if cmds.window("Extra_Options", ex=True):
        cmds.deleteUI("Extra_Options")
    
    cmds.window("Extra_Options", title="Extra Options", wh=[344, 242], s=False)
    cmds.formLayout("formLayout", numberOfDivisions=100, w=343, h=240)
    
    cmds.button("Generate_Code_Button", l="Generate Code", recomputeSize = True, bgc=[0.6220035095750363, 1.0, 0.7237659266041047], h = 44, w = 110,  parent ="formLayout", command="generateCode()",
    ann="It isolates the code from the UI, so you can put it on a shelf or add it to a marking menu, and you don't have to come back to the UI every time.\nThere's 2 ways to use this.\n"
    "Specific setup:  If you select the controls in the scene as if you were applying the setup, when you hit generate it'll store the selection into the code, so you don't have to select them every time.\n"
    "General setup:  If you have nothing selected in the scene and hit generate, it'll produce a generic version of the code, and you'll have to select the controls every time before executing the code, but it's more flexible.\n"
    "Important note:  Whatever values you have for the settings in the main window, those values will be stored within the code you generate.")
    formLayout("Generate_Code_Button", 17, 16)
    
    cmds.radioButtonGrp("GenerateCodeOptions_RadioB", vr=True, numberOfRadioButtons = 3, en1=True, l1="FK to IK", l2="IK to FK", l3="Delete Setup", parent="formLayout")
    cmds.radioButtonGrp("GenerateCodeOptions_RadioB", e=True, select=1)
    formLayout("GenerateCodeOptions_RadioB", 11.5, 135)
    
    cmds.scrollField("GenerateCodeOutputWindow", width=312, height=150)
    formLayout("GenerateCodeOutputWindow", 75, 16)
    
    cmds.showWindow("Extra_Options")

userInterface()

