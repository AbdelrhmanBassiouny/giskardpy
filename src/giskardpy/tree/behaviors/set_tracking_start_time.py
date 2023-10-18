import rospy
from py_trees import Status
from sensor_msgs.msg import JointState

from giskardpy.god_map import god_map
from giskardpy.tree.behaviors.plugin import GiskardBehavior
from giskardpy.tree.behaviors.sync_joint_state import SyncJointState
from giskardpy.utils import logging


class SetTrackingStartTime(GiskardBehavior):
    def __init__(self, name, offset: float = 0.5):
        super().__init__(name)
        self.offset = rospy.Duration(offset)

    def compute_time_offset(self) -> rospy.Duration:
        sync_node = god_map.tree_manager.get_nodes_of_type(SyncJointState)
        topic_name = sync_node[0].joint_state_topic
        msg = rospy.wait_for_message(topic_name, JointState, rospy.Duration(5))
        current_time = rospy.get_rostime()
        return current_time - msg.header.stamp

    @profile
    def initialise(self):
        super().initialise()
        delay = rospy.Duration(0)
        # delay = self.compute_time_offset()
        god_map.time_delay = delay
        if abs(delay.to_sec()) > 0.5:
            logging.logwarn(f'delay between joint states and current time is {delay.to_sec()}, compensating the offset.')
        god_map.tracking_start_time = rospy.get_rostime() + self.offset - delay

    @profile
    def update(self):
        return Status.SUCCESS
