import difflib
import inspect
import itertools
import json
import traceback
from collections import OrderedDict
from collections import defaultdict
from time import time

from giskard_msgs.msg import MoveCmd, CollisionEntry
from py_trees import Status

import giskardpy.constraints
import giskardpy.identifier as identifier
from giskardpy.constraints import SelfCollisionAvoidance, ExternalCollisionAvoidance
from giskardpy.data_types import FreeVariable
from giskardpy.exceptions import ImplementationException, UnknownConstraintException, InvalidGoalException, \
    ConstraintInitalizationException, GiskardException
from giskardpy.logging import loginfo
from giskardpy.plugin_action_server import GetGoal
from giskardpy.utils import convert_ros_message_to_dictionary, convert_dictionary_to_ros_message


class GoalToConstraints(GetGoal):
    # FIXME no error msg when constraint has missing parameter
    def __init__(self, name, as_name):
        GetGoal.__init__(self, name, as_name)
        self.used_joints = set()

        self.controlled_joints = set()
        self.controllable_links = set()
        self.last_urdf = None
        self.allowed_constraint_types = {x[0]: x[1] for x in inspect.getmembers(giskardpy.constraints) if
                                         inspect.isclass(x[1])}

        self.rc_prismatic_velocity = self.get_god_map().get_data(identifier.rc_prismatic_velocity)
        self.rc_continuous_velocity = self.get_god_map().get_data(identifier.rc_continuous_velocity)
        self.rc_revolute_velocity = self.get_god_map().get_data(identifier.rc_revolute_velocity)
        self.rc_other_velocity = self.get_god_map().get_data(identifier.rc_other_velocity)

    def initialise(self):
        self.get_god_map().set_data(identifier.collision_goal, None)
        self.clear_blackboard_exception()

    @profile
    def update(self):
        # TODO make this interruptable
        # TODO try catch everything

        move_cmd = self.get_god_map().get_data(identifier.next_move_goal)  # type: MoveCmd
        if not move_cmd:
            return Status.FAILURE

        self.get_god_map().set_data(identifier.goals, {})

        self.get_robot().create_constraints(self.get_god_map())

        self.soft_constraints = {}
        self.vel_constraints = {}
        self.debug_expr = {}
        if not (self.get_god_map().get_data(identifier.check_reachability)):
            self.get_god_map().set_data(identifier.maximum_collision_threshold, 0)
            self.add_collision_avoidance_soft_constraints(move_cmd.collisions)

        try:
            self.parse_constraints(move_cmd)
        except AttributeError:
            self.raise_to_blackboard(InvalidGoalException(u'couldn\'t transform goal'))
            traceback.print_exc()
            return Status.SUCCESS
        except Exception as e:
            self.raise_to_blackboard(e)
            traceback.print_exc()
            return Status.SUCCESS

        self.get_god_map().set_data(identifier.collision_goal, move_cmd.collisions)
        self.get_god_map().set_data(identifier.constraints, self.soft_constraints)
        self.get_god_map().set_data(identifier.vel_constraints, self.vel_constraints)
        self.get_god_map().set_data(identifier.debug_expressions, self.debug_expr)
        self.get_blackboard().runtime = time()

        controlled_joints = self.get_robot().controlled_joints

        if (self.get_god_map().get_data(identifier.check_reachability)):
            # FIXME reachability check is broken
            pass
        else:
            joint_constraints = OrderedDict(((self.robot.get_name(), k), self.robot._joint_constraints[k]) for k in
                                            controlled_joints)

        self.get_god_map().set_data(identifier.free_variables, joint_constraints)

        return Status.SUCCESS

    def parse_constraints(self, cmd):
        """
        :type cmd: MoveCmd
        :rtype: dict
        """
        loginfo(u'parsing goal message')
        for constraint in itertools.chain(cmd.constraints, cmd.joint_constraints, cmd.cartesian_constraints):
            try:
                loginfo(u'adding constraint of type: \'{}\''.format(constraint.type))
                C = self.allowed_constraint_types[constraint.type]
            except KeyError:
                matches = ''
                for s in self.allowed_constraint_types.keys():
                    sm = difflib.SequenceMatcher(None, str(constraint.type).lower(), s.lower())
                    ratio = sm.ratio()
                    if ratio >= 0.5:
                        matches = matches + s + '\n'
                if matches != '':
                    raise UnknownConstraintException(
                        u'unknown constraint {}. did you mean one of these?:\n{}'.format(constraint.type, matches))
                else:
                    available_constraints = '\n'.join([x for x in self.allowed_constraint_types.keys()]) + '\n'
                    raise UnknownConstraintException(
                        u'unknown constraint {}. available constraint types:\n{}'.format(constraint.type,
                                                                                         available_constraints))

            try:
                if hasattr(constraint, u'parameter_value_pair'):
                    parsed_json = json.loads(constraint.parameter_value_pair)
                    params = self.replace_jsons_with_ros_messages(parsed_json)
                else:
                    raise ConstraintInitalizationException(u'Only the json interface is supported at the moment. Create an issue if you want it.')
                    # params = convert_ros_message_to_dictionary(constraint)
                    # del params[u'type']

                c = C(self.god_map, control_horizon=self.get_god_map().unsafe_get_data(identifier.control_horizon), **params)
            except Exception as e:
                traceback.print_exc()
                doc_string = C.__init__.__doc__
                error_msg = u'Initialization of "{}" constraint failed: \n {} \n'.format(C.__name__, e)
                if doc_string is not None:
                    error_msg = error_msg + doc_string
                if not isinstance(e, GiskardException):
                    raise ConstraintInitalizationException(error_msg)
                raise e
            try:
                soft_constraints, vel_constraints = c.get_constraints()
                self.soft_constraints.update(soft_constraints)
                self.vel_constraints.update(vel_constraints)
                self.debug_expr.update(c.debug_expressions)
            except Exception as e:
                traceback.print_exc()
                if not isinstance(e, GiskardException):
                    raise ConstraintInitalizationException(e)
                raise e
        loginfo(u'done parsing goal message')

    def replace_jsons_with_ros_messages(self, d):
        # TODO find message type
        for key, value in d.items():
            if isinstance(value, dict) and 'message_type' in value:
                d[key] = convert_dictionary_to_ros_message(value)
        return d


    def add_collision_avoidance_soft_constraints(self, collision_cmds):
        """
        Adds a constraint for each link that pushed it away from its closest point.
        :type collision_cmds: list of CollisionEntry
        """
        # FIXME this only catches the most obvious cases
        soft_threshold = None
        for collision_cmd in collision_cmds:
            if collision_cmd.type == CollisionEntry.AVOID_ALL_COLLISIONS or \
                    self.get_world().is_avoid_all_collision(collision_cmd):
                soft_threshold = collision_cmd.min_dist

        if not collision_cmds or not self.get_world().is_allow_all_collision(collision_cmds[-1]):
            self.add_external_collision_avoidance_constraints(soft_threshold_override=soft_threshold)
        if not collision_cmds or (not self.get_world().is_allow_all_collision(collision_cmds[-1]) and
                                  not self.get_world().is_allow_all_self_collision(collision_cmds[-1])):
            self.add_self_collision_avoidance_constraints()

    def add_external_collision_avoidance_constraints(self, soft_threshold_override=None):
        soft_constraints = {}
        vel_constraints = {}
        debug_expr = {}
        number_of_repeller = self.get_god_map().get_data(identifier.external_collision_avoidance_repeller)
        number_of_repeller_eef = self.get_god_map().get_data(identifier.external_collision_avoidance_repeller_eef)
        eef_joints = self.get_robot().get_controlled_leaf_joints()
        maximum_distance = self.get_god_map().get_data(identifier.maximum_collision_threshold)
        # TODO add root joint?
        remaining_joints = [joint_name for joint_name in self.get_robot().controlled_joints
                            if joint_name not in eef_joints]
        control_horizon = self.get_god_map().get_data(identifier.control_horizon)
        for joint_name in remaining_joints:
            child_links = self.get_robot().get_directly_controllable_collision_links(joint_name)
            if child_links:
                for i in range(number_of_repeller):
                    child_link = self.get_robot().get_child_link_of_joint(joint_name)
                    hard_threshold = self.get_god_map().get_data(identifier.external_collision_avoidance_distance +
                                                                [joint_name, u'hard_threshold'])
                    if soft_threshold_override is not None:
                        soft_threshold = soft_threshold_override
                    else:
                        soft_threshold = self.get_god_map().get_data(identifier.external_collision_avoidance_distance +
                                                                    [joint_name, u'soft_threshold'])
                    maximum_distance = max(maximum_distance, soft_threshold)
                    constraint = ExternalCollisionAvoidance(self.god_map, child_link,
                                                            control_horizon=control_horizon,
                                                            hard_threshold=hard_threshold,
                                                            soft_threshold=soft_threshold,
                                                            idx=i,
                                                            num_repeller=number_of_repeller)
                    c, c_vel = constraint.get_constraints()
                    soft_constraints.update(c)
                    vel_constraints.update(c_vel)
                    debug_expr.update(constraint.debug_expressions)

        for joint_name in eef_joints:
            child_link = self.get_robot().get_child_link_of_joint(joint_name)
            for i in range(number_of_repeller_eef):
                hard_threshold = self.get_god_map().get_data(identifier.external_collision_avoidance_distance +
                                                             [joint_name, u'hard_threshold'])
                if soft_threshold_override is not None:
                    soft_threshold = soft_threshold_override
                else:
                    soft_threshold = self.get_god_map().get_data(identifier.external_collision_avoidance_distance +
                                                                 [joint_name, u'soft_threshold'])
                maximum_distance = max(maximum_distance, soft_threshold)
                constraint = ExternalCollisionAvoidance(self.god_map, child_link,
                                                        control_horizon=control_horizon,
                                                        hard_threshold=hard_threshold,
                                                        soft_threshold=soft_threshold,
                                                        idx=i,
                                                        num_repeller=number_of_repeller_eef)
                c, c_vel = constraint.get_constraints()
                soft_constraints.update(c)
                vel_constraints.update(c_vel)
                debug_expr.update(constraint.debug_expressions)

        num_external = len(soft_constraints)
        loginfo('adding {} external collision avoidance constraints'.format(num_external))
        self.soft_constraints.update(soft_constraints)
        self.vel_constraints.update(vel_constraints)
        self.debug_expr.update(debug_expr)
        self.get_god_map().set_data(identifier.maximum_collision_threshold, maximum_distance)

    def add_self_collision_avoidance_constraints(self):
        counter = defaultdict(int)
        control_horizon = self.get_god_map().get_data(identifier.control_horizon)
        soft_constraints = {}
        vel_constraints = {}
        number_of_repeller = self.get_god_map().get_data(identifier.self_collision_avoidance_repeller)
        maximum_distance = self.get_god_map().get_data(identifier.maximum_collision_threshold)
        for link_a_o, link_b_o in self.get_robot().get_self_collision_matrix():
            link_a, link_b = self.robot.get_chain_reduced_to_controlled_joints(link_a_o, link_b_o)
            if not self.get_robot().link_order(link_a, link_b):
                link_a, link_b = link_b, link_a
            counter[link_a, link_b] += 1

        for link_a, link_b in counter:
            num_of_constraints = min(1, counter[link_a, link_b])
            for i in range(num_of_constraints):
                thresholds = self.get_god_map().get_data(identifier.self_collision_avoidance_distance)
                key = u'{}, {}'.format(link_a, link_b)
                key_r = u'{}, {}'.format(link_b, link_a)
                if key in thresholds:
                    hard_threshold = thresholds[key][u'hard_threshold']
                    soft_threshold = thresholds[key][u'soft_threshold']
                elif key_r in thresholds:
                    hard_threshold = thresholds[key_r][u'hard_threshold']
                    soft_threshold = thresholds[key_r][u'soft_threshold']
                else:
                    # TODO minimum is not the best if i reduce to the links next to the controlled chains
                    #   should probably add symbols that retrieve the values for the current pair
                    hard_threshold = min(thresholds[link_a][u'hard_threshold'],
                                         thresholds[link_b][u'hard_threshold'])
                    soft_threshold = min(thresholds[link_a][u'soft_threshold'],
                                         thresholds[link_b][u'soft_threshold'])
                maximum_distance = max(maximum_distance, soft_threshold)
                constraint = SelfCollisionAvoidance(self.god_map,
                                                    control_horizon=control_horizon,
                                                    link_a=link_a,
                                                    link_b=link_b,
                                                    hard_threshold=hard_threshold,
                                                    soft_threshold=soft_threshold,
                                                    idx=i,
                                                    num_repeller=number_of_repeller)
                c, c_vel = constraint.get_constraints()
                soft_constraints.update(c)
        loginfo('adding {} self collision avoidance constraints'.format(len(soft_constraints)))
        self.soft_constraints.update(soft_constraints)
        self.vel_constraints.update(vel_constraints)
        self.get_god_map().set_data(identifier.maximum_collision_threshold, maximum_distance)
