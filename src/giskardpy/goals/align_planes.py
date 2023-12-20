from typing import Optional, List

from geometry_msgs.msg import Vector3Stamped

import giskardpy.utils.tfwrapper as tf
from giskardpy import casadi_wrapper as w
from giskardpy.goals.goal import Goal
from giskardpy.goals.monitors.monitors import Monitor
from giskardpy.goals.tasks.task import WEIGHT_BELOW_CA, WEIGHT_ABOVE_CA, WEIGHT_COLLISION_AVOIDANCE, Task
from giskardpy.god_map import god_map
from giskardpy.utils.expression_definition_utils import transform_msg
from giskardpy.utils.logging import logwarn


class AlignPlanes(Goal):
    def __init__(self,
                 root_link: str,
                 tip_link: str,
                 goal_normal: Vector3Stamped,
                 tip_normal: Vector3Stamped,
                 root_group: Optional[str] = None,
                 tip_group: Optional[str] = None,
                 reference_velocity: float = 0.5,
                 weight: float = WEIGHT_ABOVE_CA,
                 name: Optional[str] = None,
                 start_monitors: Optional[List[Monitor]] = None,
                 hold_monitors: Optional[List[Monitor]] = None,
                 end_monitors: Optional[List[Monitor]] = None,
                 **kwargs):
        """
        This goal will use the kinematic chain between tip and root to align tip_normal with goal_normal.
        :param root_link: root link of the kinematic chain
        :param tip_link: tip link of the kinematic chain
        :param goal_normal:
        :param tip_normal:
        :param root_group: if root_link is not unique, search in this group for matches.
        :param tip_group: if tip_link is not unique, search in this group for matches.
        :param reference_velocity: rad/s
        :param weight:
        """
        if 'root_normal' in kwargs:
            logwarn('Deprecated warning: use goal_normal instead of root_normal')
            goal_normal = kwargs['root_normal']
        self.root = god_map.world.search_for_link_name(root_link, root_group)
        self.tip = god_map.world.search_for_link_name(tip_link, tip_group)
        self.reference_velocity = reference_velocity
        self.weight = weight

        self.tip_V_tip_normal = transform_msg(self.tip, tip_normal)
        self.tip_V_tip_normal.vector = tf.normalize(self.tip_V_tip_normal.vector)

        self.root_V_root_normal = transform_msg(self.root, goal_normal)
        self.root_V_root_normal.vector = tf.normalize(self.root_V_root_normal.vector)

        if name is None:
            name = f'{self.__class__.__name__}/{self.root}/{self.tip}' \
                   f'_X:{self.tip_V_tip_normal.vector.x}' \
                   f'_Y:{self.tip_V_tip_normal.vector.y}' \
                   f'_Z:{self.tip_V_tip_normal.vector.z}'
        super().__init__(name)

        task = Task('align planes')
        tip_V_tip_normal = w.Vector3(self.tip_V_tip_normal)
        root_R_tip = god_map.world.compose_fk_expression(self.root, self.tip).to_rotation()
        root_V_tip_normal = root_R_tip.dot(tip_V_tip_normal)
        root_V_root_normal = w.Vector3(self.root_V_root_normal)
        task.add_vector_goal_constraints(frame_V_current=root_V_tip_normal,
                                         frame_V_goal=root_V_root_normal,
                                         reference_velocity=self.reference_velocity,
                                         weight=self.weight)
        self.add_task(task)
        self.connect_monitors_to_all_tasks(start_monitors, hold_monitors, end_monitors)
