from rl_coach.agents.clipped_ppo_agent import ClippedPPOAgentParameters
from rl_coach.exploration_policies.ou_process import OUProcessParameters
from rl_coach.architectures.embedder_parameters import InputEmbedderParameters
from rl_coach.architectures.middleware_parameters import LSTMMiddlewareParameters
from rl_coach.architectures.layers import Dense, Conv2d
from rl_coach.base_parameters import VisualizationParameters, EmbedderScheme, PresetValidationParameters, \
    MiddlewareScheme
from rl_coach.core_types import TrainingSteps, EnvironmentEpisodes, EnvironmentSteps, GradientClippingMethod
from rl_coach.environments.robosuite_environment import RobosuiteEnvironmentParameters, RobosuiteLiftParameters, \
    RobosuiteRobotType, OptionalObservations, RobosuiteControllerType
from rl_coach.environments.environment import SingleLevelSelection
from rl_coach.filters.filter import InputFilter, NoOutputFilter, NoInputFilter
from rl_coach.filters.observation import ObservationStackingFilter, ObservationRGBToYFilter, \
    ObservationNormalizationFilter
from rl_coach.graph_managers.basic_rl_graph_manager import BasicRLGraphManager
from rl_coach.graph_managers.graph_manager import ScheduleParameters

####################
# Graph Scheduling #
####################
from rl_coach.graph_managers.mast_graph_manager import MASTGraphManager

schedule_params = ScheduleParameters()
schedule_params.improve_steps = TrainingSteps(10000000000)
schedule_params.steps_between_evaluation_periods = EnvironmentSteps(100000)
schedule_params.evaluation_steps = EnvironmentEpisodes(5)
schedule_params.heatup_steps = EnvironmentSteps(0)


# Parameters based on PPO configuration in Surreal code:
# https://github.com/SurrealAI/surreal/blob/master/surreal/main/ppo_configs.py
#
# Differences vs. Surreal:
# 1. The default Surreal implementation uses the KLD regularization with adaptive coefficient.
#    There's an option to use clipped likelihood ratio instead, but it's implementation is different from
#    Coach (and the paper): The clipping range is ADAPTIVE, based on the KLD between prev and current
#    policies. So it's a mish-mash between the clipped objective and the adaptive KL coefficient methods.
#    Coach has th option for
# 2. Surreal normalizes the GAE by mean and std
# 3. The convolution layers are shared between actor and critic
# 4. When LSTM is used, it is also shared between actor and critic
# 5. Surreal uses linear LR scheduling (1e-4 to 5e-5 over 5M iterations, updated every 100 iterations)
#    Coach only supports exponential decay for learning rate


#########
# Agent #
#########
agent_params = ClippedPPOAgentParameters()

agent_params.input_filter = InputFilter()
# Normlization filter on robot/object features (called "Z filter" in surreal for some reason)
agent_params.input_filter.add_observation_filter('measurements', 'normalize',
                                                 ObservationNormalizationFilter(clip_min=-5.0, clip_max=5.0))
agent_params.output_filter = NoOutputFilter()


#############
# Algorithm #
#############
# Surreal also normalizes GAE by mean+std, missing in Coach
agent_params.algorithm.gae_lambda = 0.97
# Surreal also adapts the clip value according to the KLD between prev and current policies. Missing in Coach
agent_params.algorithm.clip_likelihood_ratio_using_epsilon = 0.2
agent_params.algorithm.num_consecutive_playing_steps = EnvironmentSteps(1500)
agent_params.algorithm.num_steps_between_copying_online_weights_to_target = EnvironmentSteps(1500)
agent_params.algorithm.optimization_epochs = 1

###########
# Network #
###########
# Camera observation pre-processing network scheme
camera_obs_scheme = [Conv2d(16, 8, 4), Conv2d(32, 4, 2), Dense(256)]

network = agent_params.network_wrappers['main']
network.input_embedders_parameters = {
    'measurements': InputEmbedderParameters(scheme=EmbedderScheme.Empty),
    'camera': InputEmbedderParameters(scheme=camera_obs_scheme)
}

# Mode 1: Frame stacking, no LSTM in middleware
agent_params.input_filter = InputFilter()

# agent_params.input_filter.add_observation_filter('camera', 'stacking', ObservationStackingFilter(3, concat=True))
agent_params.input_filter.add_observation_filter('camera', 'grayscale', ObservationRGBToYFilter())
agent_params.input_filter.add_observation_filter('camera', 'stacking', ObservationStackingFilter(3, concat=False))

network.middleware_parameters.scheme = [Dense(300), Dense(200)]

# Mode 2: No frame stacking, LSTM middleware
# TODO: Add 2 denses after the LSTM
# network.middleware_parameters = LSTMMiddlewareParameters(number_of_lstm_cells=100, scheme=MiddlewareScheme.Empty)

network.learning_rate = 1e-4
network.l2_regularization = 0.0
network.clip_gradients = 5.0
network.batch_size = 64


###############
# Environment #
###############
task_params = RobosuiteLiftParameters()
task_params.table_full_size = (0.84, 1.25, 0.82)

env_params = RobosuiteEnvironmentParameters('lift', task_params)
env_params.robot = RobosuiteRobotType.PANDA
env_params.controller = RobosuiteControllerType.IK_POSE
env_params.base_parameters.optional_observations = OptionalObservations.CAMERA
env_params.base_parameters.camera_names = 'labview'
env_params.base_parameters.camera_depths = False
env_params.base_parameters.horizon = 200
env_params.base_parameters.ignore_done = False
env_params.frame_skip = 1

vis_params = VisualizationParameters()
vis_params.print_networks_summary = True


########
# Test #
########
preset_validation_params = PresetValidationParameters()
# preset_validation_params.trace_test_levels = ['cartpole:swingup', 'hopper:hop']

graph_manager = MASTGraphManager(agent_params=agent_params, env_params=env_params,
                                    schedule_params=schedule_params, vis_params=vis_params,
                                    preset_validation_params=preset_validation_params)