from threading import Lock, Semaphore
from typing import Optional

import rospy
from py_trees import Status
from sensor_msgs.msg import JointState

import giskardpy.utils.tfwrapper as tf
from giskardpy.data_types import JointStates
from giskardpy.god_map import god_map
from giskardpy.model.world import WorldBranch
from giskardpy.my_types import PrefixName, Derivatives
from giskardpy.tree.behaviors.plugin import GiskardBehavior
from giskardpy.utils.decorators import record_time


class SyncConfiguration2(GiskardBehavior):
    """
    Listens to a joint state topic, transforms it into a dict and writes it to the got map.
    Gets replace with a kinematic sim plugin during a parallel universe.
    """

    msg: JointState

    @record_time
    @profile
    def __init__(self, group_name: str, joint_state_topic='joint_states'):
        super().__init__(str(self))
        self.joint_state_topic = joint_state_topic
        if not self.joint_state_topic.startswith('/'):
            self.joint_state_topic = '/' + self.joint_state_topic
        super().__init__(str(self))
        self.mjs: Optional[JointStates] = None
        self.group_name = group_name
        self.lock = Lock()

    @record_time
    @profile
    def setup(self, timeout=0.0):
        self.joint_state_sub = rospy.Subscriber(self.joint_state_topic, JointState, self.cb, queue_size=1)
        return super().setup(timeout)

    def cb(self, data):
        self.msg = data

    @profile
    def initialise(self):
        self.last_time = rospy.get_rostime()
        super().initialise()

    @record_time
    @profile
    def update(self):
        for joint_name, position in zip(self.msg.name, self.msg.position):
            joint_name = PrefixName(joint_name, self.group_name)
            god_map.world.state[joint_name][Derivatives.position] = position

        return Status.SUCCESS
