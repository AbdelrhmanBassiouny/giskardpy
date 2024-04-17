#!/usr/bin/env python
import rospy

from giskardpy.configs.behavior_tree_config import ClosedLoopBTConfig
from giskardpy.configs.giskard import Giskard
from giskardpy.configs.iai_robots.hsr import WorldWithHSRConfig, HSRCollisionAvoidanceConfig, \
    HSRMujocoVelocityInterface, HSRMujocoPositionInterface
from giskardpy.configs.qp_controller_config import QPControllerConfig, SupportedQPSolver

if __name__ == '__main__':
    rospy.init_node('giskard')
    debug_mode = rospy.get_param('~debug_mode', False)
    giskard = Giskard(world_config=WorldWithHSRConfig(),
                      collision_avoidance_config=HSRCollisionAvoidanceConfig(),
                      robot_interface_config=HSRMujocoVelocityInterface(),
                      behavior_tree_config=ClosedLoopBTConfig(debug_mode=debug_mode),
                      qp_controller_config=QPControllerConfig(max_trajectory_length=300, qp_solver=SupportedQPSolver.gurobi))
    giskard.live()
