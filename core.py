# - * - coding: utf - 8 - * -
# PEP8 formatting

#####################################################################################
#
# Spring Magic for Maya
#
# Calculate bone chain animation by settings, support collisions and wind force
# Can work with rigging controller as well
#
# Need pringMagic.ui file to work with
# This script need also icon file support, which should be put in same folder
#
# feel free to mail me redtank@outlook.com for any bug or issue
#
# Yanbin Bai
# 2021.02
#
#####################################################################################

import math
import logging
# import copy

import pymel.core as pm
import pymel.core.datatypes as dt
import maya.cmds as cmds

import decorators
import springMath

from utility import *

from itertools import cycle
from itertools import chain
from weakref import WeakValueDictionary

from collections import OrderedDict

###################################
# spring magic
####################################

kWindObjectName = 'spring_wind'
kSpringProxySuffix = '_SpringProxy'
kCollisionPlaneSuffix = '_SpringColPlane'
kCapsuleNameSuffix = '_collision_capsule'
kNullSuffix = '_SpringNull'
# kTwistNullSuffix = '_SpringTwistNull'


class Spring:

    def __init__(self, ratio=0.5, twistRatio=0.0, tension=0.0, extend=0.0, inertia=0.0):

        self.ratio = ratio
        self.twist_ratio = twistRatio
        self.tension = tension
        self.extend = extend
        self.inertia = inertia

class SpringMagic:

    def __init__(self, startFrame, endFrame, subDiv=1.0, isLoop=False, isPoseMatch=False, isCollision=False, isFastMove=False, wipeSubframe=True):

        self.start_frame = startFrame
        self.end_frame = endFrame

        self.sub_div = subDiv
        self.is_loop = isLoop
        self.is_pose_match = isPoseMatch
        self.is_fast_move = isFastMove
        self.wipe_subframe = wipeSubframe

        self.is_collision = isCollision
        self.collision_planes_list = None

        self.wind = None

class SpringData:

    cur_position_locator = None
    prev_position_locator = None
    prev_grand_child_position_locator = None

    _instances = WeakValueDictionary()

    @property
    def Count(self):
        return len(self._instances)

    def __init__(self, springMagic, spring, transform, child, grand_child, grand_parent):
        # self.current_child_position

        self._instances[id(self)] = self

        self.springMagic = springMagic
        self.spring = spring

        self.parent = transform
        self.child = child
        self.grand_child = grand_child
        self.grand_parent = grand_parent

        self.child_position = get_translation(child)
        self.grand_child_position = get_translation(grand_child) if grand_child else None

        self.previous_child_position = self.child_position

        self.rotation = get_rotation(transform)
        self.up_vector = get_matrix(transform)[4:7]

        transform_pos = get_translation(transform)
        self.bone_length = springMath.distance(transform_pos, self.child_position)

        self.has_child_collide = False
        self.has_plane_collide = False

        # create temporary locators use for aim constraint
        if not SpringData.cur_position_locator:
            SpringData.cur_position_locator = pm.spaceLocator(name='cur_position_locator')

        if not SpringData.prev_position_locator:
            SpringData.prev_position_locator = pm.spaceLocator(name='prev_position_locator')

        if not SpringData.prev_grand_child_position_locator:
            SpringData.prev_grand_child_position_locator = pm.spaceLocator(name='prev_grand_child_position_locator')

        # Weight attribute to de/activate the aim constraint in pose match mode
        self.pairblend_weight_attribute = None
        self.aim_constraint = None

        self.__create_child_proxy()
        self.__prepare_animation_key()
        self.__create_aim_constraint()
        self.__init_pairblend_weight()

    def __del__(self):

        if self.Count == 0:
            # print('Last Counter object deleted')

            # delete temporary locators (useful, it's delete constraints at the same time)
            pm.delete(SpringData.cur_position_locator, SpringData.prev_position_locator, SpringData.prev_grand_child_position_locator)

            SpringData.cur_position_locator = None
            SpringData.prev_position_locator = None
            SpringData.prev_grand_child_position_locator = None

            # remove all spring nulls, add recursive incase name spaces
            # pm.delete(pm.ls('*' + kNullSuffix + '*', recursive=1))
        else:
            # print(self.Count, 'Counter objects remaining')
            pass

        if self.child_proxy:
            # remove spring nulls, add recursive incase name spaces
            pm.delete(pm.ls('*' + self.child_proxy + '*', recursive=1))

    def update(self, has_collision, has_hit_plane, child_pos_corrected):
        # Update current transform with the new values
        self.child_position = get_translation(self.child)
        self.grand_child_position = get_translation(self.grand_child) if self.grand_child else None
        self.previous_child_position = child_pos_corrected

        self.rotation = get_rotation(self.parent)
        self.up_vector = get_matrix(self.parent)[4:7]

        self.has_child_collide = has_collision
        self.has_plane_collide = has_hit_plane

    def __create_child_proxy(self):
        # create a null at child pos, then parent to obj parent for calculation
        child_proxy_locator_name = self.parent.name() + kNullSuffix
        child_proxy_list = pm.ls(child_proxy_locator_name)

        if not child_proxy_list:
            self.child_proxy = pm.spaceLocator(name=child_proxy_locator_name)
        else:
            self.child_proxy = child_proxy_list[0]

        self.child_proxy.getShape().setAttr('visibility', False)

        pm.parent(self.child_proxy, self.parent.getParent())
        # pm.parent(child_proxy, self.grand_parent)

        if not self.springMagic.is_pose_match:
            self.child_proxy.setTranslation(self.child.getTranslation(space='world'), space='world')
            self.child_proxy.setRotation(self.child.getRotation(space='world'), space='world')

    def __prepare_animation_key(self):
        if not self.springMagic.is_pose_match:
            # remove exists keys
            pm.cutKey(self.parent, time=(self.springMagic.start_frame, self.springMagic.end_frame + 0.99999))
            pm.cutKey(self.child, time=(self.springMagic.start_frame, self.springMagic.end_frame + 0.99999))

            # set key
            pm.setKeyframe(self.parent, attribute='rotate')

            if self.spring.extend != 0.0:
                pm.setKeyframe(self.child, attribute='tx')

    def __create_aim_constraint(self):
        # Create a constraint per transform to speed up computation, not active yet (weight=0)
        self.aim_constraint = pm.aimConstraint(SpringData.cur_position_locator, SpringData.prev_position_locator, SpringData.prev_grand_child_position_locator, self.parent, aimVector=[1, 0, 0], upVector=[0, 1, 0], maintainOffset=False, weight=0)

    def __init_pairblend_weight(self):
        # if transform rotation has no animation, set a key at start frame to force the creation of a pairblend when the aim constraint is created
        for rotation_input in ['rx', 'ry', 'rz']:
            rotation_connection = pm.listConnections(self.parent + '.' + rotation_input, d=False, s=True)

            if not rotation_connection:
                pm.setKeyframe(self.parent, attribute=rotation_input)

        pairblends = pm.listConnections(self.parent, type="pairBlend", destination=True, skipConversionNodes=True)

        # Find the pairblend connected to the aim constraint
        for pairblend in pairblends:

            connected_constraint_list = cmds.listConnections(pairblend.name(), type='constraint', destination=False)

            if self.aim_constraint.name() in connected_constraint_list:

                # Get pairblend weight connected attribute
                # return [u'joint2.blendAim1')]
                weight_attribute_list = cmds.listConnections(pairblend + '.weight', d=False, s=True, p=True)

                if weight_attribute_list:
                    self.pairblend_weight_attribute = weight_attribute_list[0]

    def set_pairblend_weight(self, blend_value):
        if self.pairblend_weight_attribute:
            pm.setAttr(self.pairblend_weight_attribute, blend_value)

    def keyframe_child_proxy(self):

        if self.child_proxy:
            # Deactivate pairblend weight
            # Aim constraint weight set to 0 is not enough, it paratizes the process
            self.set_pairblend_weight(0.0)

            self.child_proxy.setTranslation(self.child.getTranslation(space='world'), space='world')
            pm.setKeyframe(self.child_proxy, attribute='translate')
            self.child_proxy.setRotation(self.child.getRotation(space='world'), space='world')
            pm.setKeyframe(self.child_proxy, attribute='rotate')

            self.set_pairblend_weight(1.0)

    def apply_inertia(self, currentChildPosition):
        ratio = self.spring.ratio / self.springMagic.sub_div
        inertia_offset = [0.0, 0.0, 0.0]

        if self.spring.inertia > 0.0:
            bone_ref_loc_offset_dir = currentChildPosition - self.child_position
            bone_ref_loc_offset_distance = ((bone_ref_loc_offset_dir) * (1 - ratio) * (1 - self.spring.inertia)).length()

            inertia_offset = bone_ref_loc_offset_dir.normal() * (bone_ref_loc_offset_distance / self.springMagic.sub_div)

        # apply mass
        force_direction = self.child_position - self.previous_child_position
        force_distance = force_direction.length() * self.spring.inertia

        # offset position
        inertia_offset += force_direction.normal() * (force_distance / self.springMagic.sub_div)

        return inertia_offset

    def apply_wind(self, frame):
        wind_offset = [0.0, 0.0, 0.0]

        if self.springMagic.wind:
            wind_max_force = self.springMagic.wind.getAttr('MaxForce')
            wind_min_force = self.springMagic.wind.getAttr('MinForce')
            wind_frequency = self.springMagic.wind.getAttr('Frequency')

            mid_force = (wind_max_force + wind_min_force) / 2

            # get source x - axis direction in world space
            wind_direction = get_matrix(self.springMagic.wind)[:3]
            # sDirection = sObj.getMatrix()[0][:3]
            wind_direction = dt.Vector(wind_direction[0], wind_direction[1], wind_direction[2]).normal()
            wind_distance = math.sin(frame * wind_frequency) * (wind_max_force - wind_min_force) + mid_force

            # offset position
            wind_offset = wind_direction.normal() * wind_distance

        return wind_offset

    def detect_collision(self, new_obj_pos, new_child_pos, capsule_list):
        col_pre = col_cur = None

        child_pos_corrected = self.child_position

        if self.springMagic.is_collision and capsule_list:

            if preCheckCollision(new_obj_pos, self.bone_length, capsule_list):

                # check collision from previous pos to cur pos
                col_pre, col_body_pre, hitCylinder_pre = springMath.checkCollision(new_child_pos, self.child_position, capsule_list, True)

                # check collision from cur pos to previous pos
                col_cur, col_body_cur, hitCylinder_cur = springMath.checkCollision(new_child_pos, self.child_position, capsule_list, False)

                if col_pre and (col_cur is None):
                    new_child_pos = col_pre
                elif col_cur and (col_pre is None):
                    child_pos_corrected = col_cur
                elif col_pre and col_cur:

                    # move cur child pose to closest out point if both pre and cur pos are already inside of col body
                    # if distance(col_pre, new_child_pos) < distance(col_cur, new_child_pos):
                    mid_point = (self.child_position + new_child_pos) / 2

                    if springMath.distance(col_pre, mid_point) < springMath.distance(col_cur, mid_point):
                        new_child_pos = col_pre
                    else:
                        new_child_pos = col_cur

                    if self.springMagic.is_fast_move:
                        child_pos_corrected = new_child_pos

                # # draw debug locator
                # if col_pre and col_cur:
                #     locator1 = pm.spaceLocator(name=obj.name() + '_col_pre_locator_' + str(i))
                #     locator1.setTranslation(col_pre)
                #     locator1 = pm.spaceLocator(name=obj.name() + '_col_cur_locator_' + str(i))
                #     locator1.setTranslation(col_cur)

        return True if col_pre or col_cur else False, new_child_pos, child_pos_corrected

    def detect_plane_hit(self, new_obj_pos, new_child_pos, grand_parent_has_plane_collision):
        has_hit_plane = False

        if self.springMagic.is_collision and self.springMagic.collision_planes_list[0]:
            collision_plane = self.springMagic.collision_planes_list[0]
            has_plane_collision = springMath.checkPlaneCollision(new_obj_pos, new_child_pos, collision_plane)

            if has_plane_collision or grand_parent_has_plane_collision:
                new_child_pos = repeatMoveToPlane(self.parent, new_child_pos, self.child, collision_plane, 3)
                has_hit_plane = True

        return has_hit_plane, new_child_pos

    # calculate upvector by interpolation y axis for twist
    def compute_up_vector(self):
        twist_ratio = self.spring.twist_ratio / self.springMagic.sub_div

        cur_obj_yAxis = get_matrix(self.child_proxy)[4:7]
        prev_up_vector = dt.Vector(self.up_vector[0], self.up_vector[1], self.up_vector[2]).normal()
        cur_up_vector = dt.Vector(cur_obj_yAxis[0], cur_obj_yAxis[1], cur_obj_yAxis[2]).normal()

        up_vector = (prev_up_vector * (1 - twist_ratio)) + (cur_up_vector * twist_ratio)

        return up_vector

    def aim_by_ratio(self, upVector, newChildPos, childPosCorrected):
        ratio = self.spring.ratio / self.springMagic.sub_div
        tension = self.spring.tension / (1.0 / (springMath.sigmoid(1 - self.springMagic.sub_div) + 0.5))

        # print("obj: " + str(self.parent.name()))
        # print("newChildPos: " + str(newChildPos))
        # print("childPosCorrected: " + str(childPosCorrected))
        # print("grand_child_position: " + str(self.grand_child_position))
        # print("upVector: " + str(upVector))
        # print("ratio: " + str(ratio))
        # print("tension: " + str(tension))

        SpringData.cur_position_locator.setTranslation(newChildPos)
        SpringData.prev_position_locator.setTranslation(childPosCorrected)

        pm.aimConstraint(self.parent, e=True, worldUpVector=upVector)

        pm.aimConstraint(SpringData.cur_position_locator, self.parent, e=True, w=ratio)
        pm.aimConstraint(SpringData.prev_position_locator, self.parent, e=True, w=1 - ratio)

        if self.has_child_collide and self.grand_child_position and tension != 0:
            SpringData.prev_grand_child_position_locator.setTranslation(self.grand_child_position)
            pm.aimConstraint(SpringData.prev_grand_child_position_locator, self.parent, e=True, w=(1 - ratio) * tension)

        pm.setKeyframe(self.parent, attribute='rotate')

        pm.aimConstraint(SpringData.cur_position_locator, SpringData.prev_position_locator, SpringData.prev_grand_child_position_locator, self.parent, e=True, w=0.0)

    def extend_bone(self, childPosCorrected):
        if self.spring.extend != 0.0:
            child_translation = self.child.getTranslation()
            # get length between bone pos and child pos
            x2 = (childPosCorrected - get_translation(self.parent)).length()
            x3 = (self.bone_length * (1 - self.spring.extend)) + (x2 * self.spring.extend)
            self.child.setTranslation([x3, child_translation[1], child_translation[2]])
            pm.setKeyframe(self.child, attribute='tx')
        # else:
        #     self.child.setTranslation([self.bone_length, child_translation[1], child_translation[2]])

def createCollisionPlane():

    # remove exist plane
    collision_plane = get_node('*' + kCollisionPlaneSuffix + '*')

    if collision_plane:
        pm.delete(collision_plane)

    collision_plane = pm.polyPlane(name="the" + kCollisionPlaneSuffix, sx=1, sy=1, w=10, h=10, ch=1)[0]

    # one side display
    pm.setAttr(collision_plane.doubleSided, False)

    # lock scale
    pm.setAttr(collision_plane.sx, lock=True)
    pm.setAttr(collision_plane.sy, lock=True)
    pm.setAttr(collision_plane.sz, lock=True)

    pm.select(collision_plane)


def removeBody(clear=False):
    cylinder_list = getCapsule(clear)

    pm.delete(cylinder_list)

    collision_plane = get_node('*' + kCollisionPlaneSuffix + '*')

    if collision_plane:
        pm.delete(collision_plane)


def addWindObj():
    windCone = pm.cone(name=kWindObjectName)[0]

    windCone.setScale([5, 5, 5])

    pm.delete(windCone, constructionHistory=1)

    # add wind attr
    pm.addAttr(windCone, longName='MaxForce', attributeType='float')
    pm.setAttr(windCone.name() + '.MaxForce', 1, e=1, keyable=1)
    pm.addAttr(windCone, longName='MinForce', attributeType='float')
    pm.setAttr(windCone.name() + '.MinForce', 0.5, e=1, keyable=1)
    pm.addAttr(windCone, longName='Frequency', attributeType='float')
    pm.setAttr(windCone.name() + '.Frequency', 1, e=1, keyable=1)
    # pm.addAttr(windCone, longName='Wave', attributeType='float')
    # pm.setAttr(windCone.name() + '.Wave', 0.5, e=1, keyable=1)

    setWireShading(windCone, False)

    pm.makeIdentity(apply=True)
    windCone.setRotation([0, 0, 90])


def bindControls(linked_chains=False):
    selected_ctrls = pm.ls(sl=True)
    pm.select(clear=True)

    # The chains are linked, we can sort them
    if linked_chains:
        # Create list for every ctrls chains
        # ie [[ctrl1, ctrl1.1, ctrl1.2], [ctrl2, ctrl2.1, ctrl2.2, ctrl2.3]]
        all_ctrls_descendants_list = pm.listRelatives(selected_ctrls, allDescendents=True)
        top_hierarchy_ctrls_list = [x for x in selected_ctrls if x not in all_ctrls_descendants_list]

        ctrls_chains_list = map(lambda x: [x] + [y for y in pm.listRelatives(x, allDescendents=True) if y in selected_ctrls][::-1], top_hierarchy_ctrls_list)
    # No sorting possible because the controlers have no lineage
    else:
        ctrls_chains_list = [selected_ctrls]

    proxy_joint_chain_list = []

    for ctrls_list in ctrls_chains_list:

        proxy_joint_list = []

        for ctrl in ctrls_list:
            # create proxy joint in ctrl world position
            ctrl_position = pm.xform(ctrl, worldSpace=1, rp=1, q=1)

            proxyJoint = pm.joint(name=ctrl.name() + kSpringProxySuffix, position=ctrl_position, radius=0.2, roo='xyz')
            proxy_joint_list.append(proxyJoint)

        for joint in proxy_joint_list:
            # set joint orientation
            pm.joint(joint, edit=1, orientJoint='xyz', zeroScaleOrient=True)

            # Straight bones alignment
            joint.setRotation([0, 0, 0])
            joint.setAttr('rotateAxis', [0, 0, 0])
            joint.setAttr('jointOrient', [0, 0, 0])

            # Free rotation (move rotation values to joint orient values)
            # pm.makeIdentity(proxy_joint_list[idx], apply=True, t=False, r=True, s=False, pn=True)

        if proxy_joint_list:
            # parent root proxy joint to control parent
            pm.parent(proxy_joint_list[0], ctrls_list[0].getParent())

        # Necessary to start a new joint chain
        pm.select(clear=True)

        proxy_joint_chain_list += [proxy_joint_list]

        for idx, joint in enumerate(proxy_joint_list[:-1]):
            # orient joint chain
            cns = pm.aimConstraint(ctrls_list[idx + 1], proxy_joint_list[idx], aimVector=[1, 0, 0], upVector=[0, 0, 0], worldUpVector=[0, 1, 0], skip='x')
            pm.delete(cns)

        for idx, joint in enumerate(proxy_joint_list):
            pm.parentConstraint(proxy_joint_list[idx], ctrls_list[idx], maintainOffset=True)

    pm.select(proxy_joint_chain_list)


def clearBind(startFrame, endFrame):
    proxyJointLst = pm.ls(sl=True)
    pm.select(d=True)

    ctrlList = []

    for bone in proxyJointLst:
        ctrl = pm.ls(bone.name().split(kSpringProxySuffix)[0])[0]
        ctrlList.append(ctrl)

    if ctrlList:
        pm.bakeResults(*ctrlList, t=(startFrame, endFrame))

    pm.delete(proxyJointLst)


def bindPose():
    pm.runtime.GoToBindPose()


# Prepare all information to call SpringMagicMaya function
def startCompute(spring, springMagic, progression_callback=None):

    autokeyframe_state = cmds.autoKeyframe(query=True, state=True)
    cmds.autoKeyframe(state=False)

    # get selection obj
    objs = pm.ls(sl=True)

    # check objects validity
    for obj in objs:
        # has duplicate name obj
        nameCntErr = (len(pm.ls(obj.name())) > 1)

        # is a duplicate obj
        nameValidErr = (obj.name().find('|') > 0)

        if nameCntErr or nameValidErr:
            raise ValueError(obj.name() + ' has duplicate name object! Stopped!')

        obj_translation = obj.getTranslation()

        if (obj_translation[0] < 0 or abs(obj_translation[1]) > 0.001 or abs(obj_translation[2]) > 0.001) and obj.getParent() and (obj.getParent() in objs):
            pm.warning(obj.getParent().name() + "'s X axis not point to child! May get broken result!")

    # Search for collision objects
    if springMagic.is_collision:
        springMagic.collision_planes_list = [get_node('*' + kCollisionPlaneSuffix + '*')]

    # Search for a wind object
    if pm.ls(kWindObjectName):
        springMagic.wind = pm.ls(kWindObjectName)[0]

    SpringMagicMaya(objs, spring, springMagic, progression_callback)

    cmds.autoKeyframe(state=autokeyframe_state)


# @decorators.viewportOff
@decorators.gShowProgress(status="SpringMagic does his magic")
def SpringMagicMaya(objs, spring, springMagic, progression_callback=None):
    # on each frame go through all objs and do:
    # 1. make a vectorA from current obj position to previous child position
    # 2. make a vectorB from current obj position to current child position
    # 3. calculate the angle between two vectors
    # 4. rotate the obj towards vectorA base on spring value

    start_frame = springMagic.start_frame
    end_frame = springMagic.end_frame
    sub_div = springMagic.sub_div

    # remove all spring nulls, add recursive incase name spaces
    pm.delete(pm.ls('*' + kNullSuffix + '*', recursive=True))

    # get all capsules in scene
    capsule_list = getCapsule(True) if springMagic.is_collision else None

    if progression_callback:
        progression_callback(0)

    # Save object previous frame information in a ordered dict
    spring_data_dict = OrderedDict()

    # Initialize data on the first frame
    pm.currentTime(start_frame, edit=True)

    # Create a list of objects chains
    # ie [[nt.Joint(u'joint1'), nt.Joint(u'joint2'), nt.Joint(u'joint4')], [nt.Joint(u'joint7'), nt.Joint(u'joint8'), nt.Joint(u'joint10')]]
    all_joints_descendants_list = pm.listRelatives(objs, allDescendents=True, type='transform')
    top_hierarchy_joints_list = [x for x in objs if x not in all_joints_descendants_list]

    # transforms_chains_list = map(lambda x: [x] + [y for y in pm.listRelatives(x, allDescendents=True) if y in objs][::-1], top_hierarchy_joints_list)

    # Deal with the specific case of root bone with no parent.
    # The root bone is considered the driver, so we remove it from the calculation.
    transforms_chains_list = map(lambda x: ([x] if x.getParent() else []) + [y for y in pm.listRelatives(x, allDescendents=True) if y in objs][::-1], top_hierarchy_joints_list)

    # Remove empty lists
    transforms_chains_list = [x for x in transforms_chains_list if x != []]

    # Create progression bar generator values
    number_of_progession_step = 0

    if springMagic.is_pose_match:
        number_of_progession_step += end_frame - start_frame + 1

    if springMagic.is_loop:
        # Doesn't process the first frame on the first loop
        number_of_progession_step += ((end_frame - start_frame) * 2 + 1) * sub_div
    else:
        # Doesn't process the first frame
        number_of_progession_step += (end_frame - start_frame) * sub_div

    progression_increment = 100.0 / number_of_progession_step
    progression_generator = frange(progression_increment, 100.0 + progression_increment, progression_increment)

    # Create spring data for each transforms at start frame
    for transforms_chain in transforms_chains_list:

        if SpringMagicMaya.isInterrupted():
            break

        transforms_cycle = cycle(transforms_chain)

        # Prime the pump
        parent = first_transform = next(transforms_cycle)
        grand_parent = parent.getParent()
        child = next(transforms_cycle)
        grand_child = next(transforms_cycle)

        # skip end bone
        for transform in transforms_chain[:-1]:

            if SpringMagicMaya.isInterrupted():
                break

            # End of cycle iteration
            if grand_child == first_transform:
                grand_child = None

            spring_data_dict[parent.name()] = SpringData(springMagic, spring, parent, child, grand_child, grand_parent)

            grand_parent, parent, child, grand_child = parent, child, grand_child, next(transforms_cycle)

    # Save joints position over timeline
    # Parse timeline just one time
    if springMagic.is_pose_match:
        for frame in range(0, end_frame - start_frame + 1):

            if SpringMagicMaya.isInterrupted():
                break

            pm.currentTime(start_frame + frame, edit=True)

            for spring_data in spring_data_dict.values():

                if not SpringMagicMaya.isInterrupted():
                    spring_data.keyframe_child_proxy()

            progression = progression_generator.next()
            progression = clamp(progression, 0, 100)

            if progression_callback:
                progression_callback(progression)

            SpringMagicMaya.progress(progression)

    # Generate frame index
    # Skip first frame on first calculation pass
    frame_increment = 1.0 / sub_div
    frame_generator = frange(frame_increment, end_frame - start_frame + frame_increment, frame_increment)

    # On second calculation pass compute first frame
    if springMagic.is_loop:
        frame_generator = chain(frame_generator, frange(0, end_frame - start_frame + frame_increment, frame_increment))

    for frame in frame_generator:

        # print('Frame: ' + str(frame))

        if SpringMagicMaya.isInterrupted():
            break

        pm.currentTime(start_frame + frame, edit=True)

        for previous_frame_spring_data in spring_data_dict.values():

            if SpringMagicMaya.isInterrupted():
                break

            grand_parent_spring_data = None
            if previous_frame_spring_data.grand_parent and previous_frame_spring_data.grand_parent.name() in spring_data_dict.keys():
                grand_parent_spring_data = spring_data_dict[previous_frame_spring_data.grand_parent.name()]

            # get current position of parent and child
            parent_pos = get_translation(previous_frame_spring_data.parent)

            # print("obj: " + str(previous_frame_spring_data.parent.name()))

            new_child_pos = get_translation(previous_frame_spring_data.child_proxy)

            # Apply inertia
            new_child_pos += previous_frame_spring_data.apply_inertia(new_child_pos)

            # apply wind
            new_child_pos += previous_frame_spring_data.apply_wind(start_frame + frame)

            # detect collision
            has_collision, new_child_pos, child_pos_corrected = previous_frame_spring_data.detect_collision(parent_pos, new_child_pos, capsule_list)

            # detect plane collision
            grand_parent_has_plane_collision = False
            if grand_parent_spring_data:
                grand_parent_has_plane_collision = grand_parent_spring_data.has_plane_collide

            has_hit_plane, new_child_pos = previous_frame_spring_data.detect_plane_hit(parent_pos, new_child_pos, grand_parent_has_plane_collision)

            # calculate upvector by interpolation y axis for twist
            up_vector = previous_frame_spring_data.compute_up_vector()

            # apply aim constraint to do actual rotation
            previous_frame_spring_data.aim_by_ratio(up_vector, new_child_pos, child_pos_corrected)

            # Extend bone if needed (update child translation)
            previous_frame_spring_data.extend_bone(child_pos_corrected)

            # Update current transform with the new values
            previous_frame_spring_data.update(has_collision, has_hit_plane, child_pos_corrected)

            # Update the grand parent has_child_collide value
            if grand_parent_spring_data:
                grand_parent_spring_data.has_child_collide = has_collision

        progression = progression_generator.next()
        progression = clamp(progression, 0, 100)

        if progression_callback:
            progression_callback(progression)

        SpringMagicMaya.progress(progression)

    # bake result on frame
    if springMagic.wipe_subframe and not SpringMagicMaya.isInterrupted():
        transform_to_bake_list = [spring_data.parent for spring_data in spring_data_dict.values()]

        # Deactivate all pairblend otherwise bake doesn't work with animation layers
        for spring_data in spring_data_dict.values():
            spring_data.set_pairblend_weight(0.0)

        bakeAnim(transform_to_bake_list, start_frame, end_frame)


def bakeAnim(objList, startFrame, endFrame):
    pm.bakeResults(
        objList,
        t=(startFrame, endFrame),
        sampleBy=1,
        disableImplicitControl=False,
        preserveOutsideKeys=True,
        sparseAnimCurveBake=False,
        removeBakedAttributeFromLayer=False,
        bakeOnOverrideLayer=False,
        minimizeRotation=True,
        shape=False,
        simulation=False)


SM_boneTransformDict = {}


def copyBonePose():
    global SM_boneTransformDict

    for obj in pm.ls(sl=True):
        SM_boneTransformDict[obj] = [obj.getTranslation(), obj.getRotation()]


def pasteBonePose():
    global SM_boneTransformDict

    for obj in pm.ls(sl=True):
        if obj in SM_boneTransformDict.keys():

            logging.debug(SM_boneTransformDict[obj][0])

            obj.setTranslation(SM_boneTransformDict[obj][0])
            obj.setRotation(SM_boneTransformDict[obj][1])


def preCheckCollision(objPos, objLength, capsuleList):

    # print('objPos:' + str(objPos))
    # print('objLength:' + str(objLength))

    # pre check bone length compare with collision body radius
    # will improve performance if bone is far from capsule
    for capsule in capsuleList:
        capsule_children_list = pm.listRelatives(capsule, children=1, type='transform')

        p = capsule_children_list[0].getTranslation(space='world')
        q = capsule_children_list[1].getTranslation(space='world')
        r = capsule.getAttr('scaleZ')

        bone_to_capsule_distance = springMath.dist_to_line(p, q, objPos)

        # print('p:' + str(p))
        # print('q:' + str(q))
        # print('r:' + str(r))
        # print('boneToCapsuleDistance:' + str(bone_to_capsule_distance))

        # means close enough to have a hit change
        if bone_to_capsule_distance < objLength + r:
            return True

    return False


def repeatMoveToPlane(obj, objPos, objTarget, colPlane, times):
    # Y axis direction of plane
    n = dt.Vector(get_matrix(colPlane)[4:7])
    q = get_translation(colPlane)
    d = n.dot(q)

    # for i in range(times):
    #     pt = objPos
    #     obj.setTranslation(proj_pt_to_plane(pt, n, d), space='world')
    #     if (i + 1) != times:
    #         obj.setTranslation(get_translation(objTarget), space='world')
    pt = objPos
    outPos = springMath.proj_pt_to_plane(pt, n, d)

    return outPos


def setWireShading(obj, tmp):
    obj.getShape().overrideEnabled.set(True)
    obj.getShape().overrideShading.set(False)

    if tmp:
        obj.getShape().overrideDisplayType.set(1)


def addCapsuleSphereConstraint(sphereObj):
    # create a locator and make sphere follow it
    locator = pm.spaceLocator(name=sphereObj.name() + '_locator' + kCapsuleNameSuffix)

    locator.setTranslation(sphereObj.getTranslation())
    locator.setRotation(sphereObj.getRotation())
    locator.getShape().setAttr('visibility', False)

    pm.parentConstraint(locator, sphereObj)

    return locator


def createCapsuleGeometry(size):
    # create geometry
    cylinder, cylinder_history = pm.cylinder(radius=size, sections=8, heightRatio=3)
    pm.rename(cylinder.name(), cylinder.name() + kCapsuleNameSuffix)

    sphereA, sphereA_history = pm.sphere(radius=size, endSweep=180, sections=4)
    pm.rename(sphereA.name(), sphereA.name() + kCapsuleNameSuffix)

    sphereB, sphereB_history = pm.sphere(radius=size, endSweep=180, sections=4)
    pm.rename(sphereB.name(), sphereB.name() + kCapsuleNameSuffix)

    # set to wireframe shader
    setWireShading(cylinder, False)
    setWireShading(sphereA, True)
    setWireShading(sphereB, True)

    # build a capsule with geometry
    cylinder.setAttr('rotateZ', 90)
    sphereA.setAttr('translateY', -1.5 * size)
    sphereB.setAttr('rotateZ', 180)
    sphereB.setAttr('translateY', 1.5 * size)

    # add constrain
    locatorA = addCapsuleSphereConstraint(sphereA)
    locatorB = addCapsuleSphereConstraint(sphereB)

    pm.parent(locatorA, cylinder)
    pm.parent(locatorB, cylinder)

    pm.parent(sphereA, cylinder)
    pm.parent(sphereB, cylinder)

    sphereA.setAttr('inheritsTransform', False)
    sphereB.setAttr('inheritsTransform', False)

    pm.connectAttr(cylinder.scaleY, (sphereA_history.name() + '.radius'))
    pm.connectAttr(cylinder.scaleY, (sphereB_history.name() + '.radius'))
    pm.connectAttr(cylinder.scaleY, cylinder.scaleZ)

    return cylinder


def getCapsule(getAll):
    if getAll:
        nurbsTransLst = pm.ls(type='transform')
    else:
        nurbsTransLst = pm.ls(sl=True)

    nurbsSurfaceLst = []
    for obj in nurbsTransLst:
        if obj.getShape() and (pm.nodeType(obj.getShape()) == 'nurbsSurface'):
            nurbsSurfaceLst.append(obj)

    cylinderLst = []
    for obj in nurbsTransLst:
        if 'ylinder' in obj.name() and kCapsuleNameSuffix in obj.name():
            cylinderLst.append(obj)

    return cylinderLst


def addCapsuleBody():
    # create capsule body for collision
    # place capsule at ori point of nothing selected in scene
    # place capsule match with object position and rotation if select scene object
    collisionBoneList = []
    objs = pm.ls(sl=True)

    for obj in objs:
        children = pm.listRelatives(obj, children=1)

        # only add capsule to the obj which has child
        if children:
            collisionBoneList.append([obj, children[0]])

    if collisionBoneList:
        for couple in collisionBoneList:
            baseBone = couple[0]
            endBone = couple[1]
            capsule = createCapsuleGeometry(1)

            pm.parent(capsule, baseBone)
            # match capsule to bone
            endBoneTrans = endBone.getTranslation()
            capsule.setTranslation(endBoneTrans * 0.5)
            capsule.setAttr('scaleX', endBoneTrans[0] / 3)
            capsule.setAttr('scaleY', endBoneTrans[0] / 3)
            cns = pm.aimConstraint(endBone, capsule, aimVector=[1, 0, 0])
            pm.delete(cns)

    else:
        capsule = createCapsuleGeometry(1)
        capsule.setAttr('scaleX', 10)
        capsule.setAttr('scaleY', 10)
        pm.select(clear=1)

