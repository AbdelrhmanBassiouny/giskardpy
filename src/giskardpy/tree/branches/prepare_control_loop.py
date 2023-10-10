from py_trees import Sequence

from giskard_msgs.msg import MoveFeedback
from giskardpy.tree.behaviors.cleanup import CleanUpPlanning
from giskardpy.tree.behaviors.compile_monitors import CompileMonitors
from giskardpy.tree.behaviors.init_qp_controller import InitQPController
from giskardpy.tree.behaviors.new_trajectory import NewTrajectory
from giskardpy.tree.behaviors.plot_goal_graph import PlotGoalGraph
from giskardpy.tree.behaviors.publish_feedback import PublishFeedback
from giskardpy.tree.behaviors.ros_msg_to_goal import ParseActionGoal
from giskardpy.tree.behaviors.set_tracking_start_time import SetTrackingStartTime
from giskardpy.tree.decorators import success_is_failure


class PrepareControlLoop(Sequence):
    def __init__(self, name: str = 'prepare control loop'):
        super().__init__(name)
        self.add_child(PublishFeedback('publish feedback2',
                                       MoveFeedback.PLANNING))
        self.add_child(CleanUpPlanning('CleanUpPlanning'))
        self.add_child(NewTrajectory('NewTrajectory'))
        self.add_child(ParseActionGoal('RosMsgToGoal'))
        self.add_child(InitQPController('InitQPController'))
        self.add_child(CompileMonitors())
        self.add_child(SetTrackingStartTime('start tracking time'))

    def add_plot_goal_graph(self):
        self.add_child(PlotGoalGraph())