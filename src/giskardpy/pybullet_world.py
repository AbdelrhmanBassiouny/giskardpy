import pybullet as p
from collections import namedtuple, OrderedDict, defaultdict
from itertools import combinations
from pybullet import JOINT_REVOLUTE, JOINT_PRISMATIC, JOINT_PLANAR, JOINT_SPHERICAL
import os
import errno

from geometry_msgs.msg import Vector3, PoseStamped, Point, Quaternion
from numpy.random.mtrand import seed
from std_msgs.msg import ColorRGBA
from urdf_parser_py.urdf import URDF, Box, Sphere, Cylinder
from visualization_msgs.msg import Marker

import giskardpy
# from giskardpy import DEBUG
from giskardpy.exceptions import UnknownBodyException, RobotExistsException, DuplicateNameException
from giskardpy.data_types import SingleJointState
import numpy as np

from giskardpy.pybullet_world_object import PyBulletWorldObject
from giskardpy.pybullet_wrapper import ContactInfo, deactivate_rendering, activate_rendering
from giskardpy.urdf_object import URDFObject
from giskardpy.utils import keydefaultdict, suppress_stdout, NullContextManager, resolve_ros_iris_in_urdf, \
    write_to_tmp
import hashlib

from giskardpy.world import World


# TODO globally define map
MAP = u'map'



class PyBulletWorld(World):
    """
    Wraps around the shitty pybullet api.
    """
    ground_plane_name = u'ground_plane'
    hack_name = u'pybullet_hack'

    def __init__(self, enable_gui=False, path_to_data_folder=u''):
        """
        :type enable_gui: bool
        :param path_to_data_folder: location where compiled collision matrices are stored
        :type path_to_data_folder: str
        """
        super(PyBulletWorld, self).__init__()
        self._gui = enable_gui
        self._object_names_to_objects = {}
        self._object_id_to_name = {}
        self._robot = None
        self.path_to_data_folder = path_to_data_folder

    # def spawn_robot_from_urdf_file(self, robot_name, urdf_file, controlled_joints, base_pose=Transform()):
    #     """
    #     Spawns a new robot into the world, reading its URDF from disc.
    #     :param robot_name: Name of the new robot to spawn.
    #     :type robot_name: str
    #     :param urdf_file: Valid and existing filename of the URDF to load, e.g. '/home/foo/bar/pr2.urdf'
    #     :type urdf_file: str
    #     :param base_pose: Pose at which to spawn the robot.
    #     :type base_pose: Transform
    #     """
    #     with open(urdf_file, u'r') as f:
    #         self.spawn_robot_from_urdf(robot_name, f.read(), controlled_joints, base_pose)

    def add_robot(self, robot, controlled_joints=None, base_pose=None):
        """
        :type robot_name: str
        :param urdf: URDF to spawn as loaded XML string.
        :type urdf: str
        :type base_pose: Transform
        """
        # deactivate_rendering()
        super(PyBulletWorld, self).add_robot(robot, controlled_joints, base_pose)
        # activate_rendering()

    # def spawn_object_from_urdf_str(self, name, urdf, base_pose=None):
    #     """
    #     :type name: str
    #     :param urdf: Path to URDF file, or content of already loaded URDF file.
    #     :type urdf: str
    #     :type base_pose: Transform
    #     """
    #     if self.has_object(name):
    #         raise DuplicateNameException(u'object with name "{}" already exists'.format(name))
    #     if self.has_robot() and self.get_robot().name == name:
    #         raise DuplicateNameException(u'robot with name "{}" already exists'.format(name))
    #     self.deactivate_rendering()
    #     self._object_names_to_objects[name] = PyBulletWorldObj(name, urdf, [], base_pose, False)
    #     self._object_id_to_name[self._object_names_to_objects[name].id] = name
    #     self.activate_rendering()
    #     print(u'object {} added to pybullet world'.format(name))

    # def spawn_object_from_urdf_file(self, object_name, urdf_file, base_pose=Transform()):
    #     """
    #     Spawns a new robot into the world, reading its URDF from disc.
    #     :param robot_name: Name of the new robot to spawn.
    #     :type robot_name: str
    #     :param urdf_file: Valid and existing filename of the URDF to load, e.g. '/home/foo/bar/pr2.urdf'
    #     :type urdf_file: str
    #     :param base_pose: Pose at which to spawn the robot.
    #     :type base_pose: Transform
    #     """
    #     with open(urdf_file, u'r') as f:
    #         self.spawn_object_from_urdf_str(object_name, f.read(), base_pose)

    # def spawn_urdf_object(self, urdf_object, base_pose=Transform()):
    #     """
    #     Spawns a new object into the Bullet world at a given pose.
    #     :param urdf_object: New object to add to the world.
    #     :type urdf_object: UrdfObject
    #     :param base_pose: Pose at which to spawn the object.
    #     :type base_pose: Transform
    #     """
    #     self.spawn_object_from_urdf_str(urdf_object.name, to_urdf_string(urdf_object), base_pose)

    # def attach_object(self, object_, parent_link, transform):
    #     """
    #     :type object_: UrdfObject
    #     :type parent_link: str
    #     :param transform:
    #     :return:
    #     """
    #     if self.has_object(object_.name):
    #         object_ = self.get_object(object_.name)
    #         # self.get_robot().attach_urdf(object_, parent_link)
    #         # FIXME
    #         transform = None
    #         self.delete_object(object_.name)
    #         # raise DuplicateNameException(
    #         #     u'Can\'t attach existing object \'{}\'.'.format(object.name))
    #     self.get_robot().attach_urdf(object_, parent_link, transform)

    def __get_pybullet_object_id(self, name):
        return self._object_names_to_objects[name].id

    # def get_object_name(self, id):
    #     return self._object_id_to_name[id]

    # def remove_robot(self):
    #     if not self.has_robot():
    #         p.removeBody(self._robot.id)
    #         self._robot = None

    def remove_object(self, name):
        """
        Deletes an object with a specific name from the world.
        :type name: str
        """
        super(PyBulletWorld, self).remove_object(name)
        # if not self.has_object(name):
        #     raise UnknownBodyException(u'Cannot delete unknown object {}'.format(name))
        # self.__deactivate_rendering()
        # p.removeBody(self.__get_pybullet_object_id(name))
        # self.__activate_rendering()
        # del (self._object_id_to_name[self.__get_pybullet_object_id(name)])
        # del (self._object_names_to_objects[name])
        # print(u'object {} deleted from pybullet world'.format(name))

    # def delete_all_objects(self, remaining_objects=(u'plane',)):
    #     """
    #     Deletes all objects in world. Optionally, one can specify a list of objects that shall remain in the world.
    #     :param remaining_objects: Names of objects that shall remain in the world.
    #     :type remaining_objects: list
    #     """
    #     for object_name in self.get_object_names():
    #         if not object_name in remaining_objects:
    #             self.delete_object(object_name)

    def check_collisions(self, cut_off_distances):
        """
        :param cut_off_distances: (robot_link, body_b, link_b) -> cut off distance. Contacts between objects not in this
                                    dict or further away than the cut off distance will be ignored.
        :type cut_off_distances: dict
        :param self_collision_d: distances grater than this value will be ignored
        :type self_collision_d: float
        :type enable_self_collision: bool
        :return: (robot_link, body_b, link_b) -> ContactInfo
        :rtype: dict
        """
        # TODO I think I have to multiply distance with something
        collisions = defaultdict(lambda: None)
        for k, distance in cut_off_distances.items():
            (robot_link, body_b, link_b) = k
            robot_link_id = self.get_robot().link_name_to_id[robot_link]
            if self.get_robot().name == body_b:
                object_id = self.get_robot().id
                link_b_id = self.get_robot().link_name_to_id[link_b]
            else:
                object_id = self.__get_pybullet_object_id(body_b)
                link_b_id = self.get_object(body_b).link_name_to_id[link_b]
            # FIXME redundant checks for robot link pairs
            contacts = [ContactInfo(*x) for x in p.getClosestPoints(self._robot.id, object_id,
                                                                    distance * 3,
                                                                    robot_link_id, link_b_id)]
            if len(contacts) > 0:
                collisions.update({k: min(contacts, key=lambda x: x.contact_distance)})
                # asdf = self.should_switch(contacts[0])
                pass
        return collisions

    def __should_flip_contact_info(self, contact_info):
        """
        :type contact_info: ContactInfo
        :rtype: bool
        """
        contact_info2 = ContactInfo(*min(p.getClosestPoints(contact_info.body_unique_id_b,
                                                            contact_info.body_unique_id_a,
                                                            abs(contact_info.contact_distance) * 1.05,
                                                            contact_info.link_index_b, contact_info.link_index_a),
                                         key=lambda x: x[8]))
        if not np.isclose(contact_info2.contact_normal_on_b, contact_info.contact_normal_on_b).all():
            return False
        pa = np.array(contact_info.position_on_a)
        # pb = np.array(contact_info.position_on_b)

        self.__move_hack(pa)
        try:
            contact_info3 = ContactInfo(*[x for x in p.getClosestPoints(self.__get_pybullet_object_id(u'pybullet_sucks'),
                                                                        contact_info.body_unique_id_a, 0.001) if
                                          np.allclose(x[8], -0.005)][0])
            if contact_info3.body_unique_id_b == contact_info.body_unique_id_a and \
                    contact_info3.link_index_b == contact_info.link_index_a:
                return False
        except Exception as e:
            return True
        return True

    def __flip_contact_info(self, contact_info):
        return ContactInfo(contact_info.contact_flag,
                           contact_info.body_unique_id_a, contact_info.body_unique_id_b,
                           contact_info.link_index_a, contact_info.link_index_b,
                           contact_info.position_on_b, contact_info.position_on_a,
                           (-np.array(contact_info.contact_normal_on_b)).tolist(), contact_info.contact_distance,
                           contact_info.normal_force,
                           contact_info.lateralFriction1, contact_info.lateralFrictionDir1,
                           contact_info.lateralFriction2,
                           contact_info.lateralFrictionDir2)

    def setup(self):
        self.__add_ground_plane()
        self.__add_pybullet_bug_fix_hack()

    def soft_reset(self):
        super(PyBulletWorld, self).soft_reset()
        self.__add_ground_plane()
        self.__add_pybullet_bug_fix_hack()

    def __add_ground_plane(self):
        """
        Adds a ground plane to the Bullet World.
        """
        if not self.has_object(self.ground_plane_name):
            plane = PyBulletWorldObject.from_urdf_file(self.path_to_data_folder + u'/urdf/ground_plane.urdf')
            plane.set_name(self.ground_plane_name)
            self.add_object(plane)


    def __add_pybullet_bug_fix_hack(self):
        if not self.has_object(self.hack_name):
            plane = PyBulletWorldObject.from_urdf_file(self.path_to_data_folder + u'/urdf/tiny_ball.urdf')
            plane.set_name(self.hack_name)
            self.add_object(plane)

    def __move_hack(self, position):
        self.get_object(self.hack_name).set_base_pose(position)

    def get_objects(self):
        objects = super(PyBulletWorld, self).get_objects()
        hidden_objects = [self.ground_plane_name, self.hack_name]
        return {k:v for k,v in objects.items() if k not in hidden_objects}




