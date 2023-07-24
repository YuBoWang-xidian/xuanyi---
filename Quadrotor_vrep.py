# -*- coding: utf-8 -*-
"""
Created on Fri Sep 10 22:43:05 2021

@author: 14791
"""

import vrep
import numpy as np



class BundleType(object):
    """
    This class bundles many fields, similar to a record or a mutable
    namedtuple.
    """
    def __init__(self, variables):
        for var, val in variables.items():
            object.__setattr__(self, var, val)

    # Freeze fields so new ones cannot be set.
    def __setattr__(self, key, value):
        if not hasattr(self, key):
            raise AttributeError("%r has no attribute %s" % (self, key))
        object.__setattr__(self, key, value)


class EnvSpec(BundleType):
    """ Collection of iteration variables. """
    def __init__(self):
        variables = {
            'action_space': None,       # object.
            'observation_space': None,  # object.
        }
        BundleType.__init__(self, variables)


class Dimension(BundleType):
    """ Collection of iteration variables. """
    def __init__(self):
        variables = {
            'flat_dim': None,
            'low': None,
            'high': None,
            'shape':None,# object.
        }
        BundleType.__init__(self, variables)


class SpaceRobot3link(object):

    def __init__(self):
        self.handles = {}
        self.action_dims = 2
        self.obs_dims = 2
        self.goal_dims=3
        self._max_episode_steps=100

        self.env_spec = EnvSpec()
        self.env_spec.action_space = Dimension()
        self.env_spec.observation_space = Dimension()
        self.env_spec.action_space.low = -2
        self.env_spec.action_space.high =2
        self.env_spec.action_space.shape =[self.action_dims,1]
        self.env_spec.action_space.flat_dim = self.action_dims
        self.env_spec.observation_space.flat_dim = self.obs_dims

        self.joint_target_velocities = np.ones(self.action_dims) * 10000     # make it gigantic enough to be the torque mode
        self.cur_obs = None         # current observation s_t
        self.num_episode = 1
        self.t = 1                          # the current time t for a trajectory.
        self._max_torque=1000
       

    @property
    def spec(self):
        return self.env_spec

    def _init_vrep(self):       # get clientID
        vrep.simxFinish(-1)         # end all running communication threads
        clientID = vrep.simxStart('127.0.0.1', 19997, True, False, 5000, 0)       # get the clientID to communicate with the current V-REP
        self.clientID = clientID

        if self.clientID != -1:         # clientID = -1 means connection failed.(time-out)
            print('\n' + 'Connected to remote V-REP server.')
        else:
            print('\n' + 'Connection time-out !')
            raise Exception('Connection Failed !')

        vrep.simxSynchronous(self.clientID, True)       # enable synchronous operation to V-REP

    def _get_handles(self):       # get handles of objects in V-REP
        
        base_handles = [vrep.simxGetObjectHandle(self.clientID, 'Quadrotor', vrep.simx_opmode_blocking)[1]]
        sensor_names =['Vision_sensor']
        sensor_handles = [vrep.simxGetObjectHandle(self.clientID, sensor_names[i], vrep.simx_opmode_blocking)[1]
                         for i in range(len(sensor_names))]

        self.handles['sensors']=sensor_handles
        self.handles['base'] = base_handles
        # handles dict
   
        

    def _configure_initial_state(self, condition=0):
        # TODO: if we want to train the policy and Q-function under different initial configurations.
        pass

    def _get_observation(self):     # get current observations s_t
        state = np.zeros(12)
        # state is [θ1, θ2, θ3, ω1, ω2, ω3, Base_α, Base_β, Base_γ,
        #           Base_x, Base_y, Base_z, Vx, Vy, Vz, dα, dβ, dγ]

        
        
        Base_pose = [vrep.simxGetObjectOrientation(self.clientID, self.handles['base'][0],
                                                   -1, vrep.simx_opmode_blocking)[1]]
        state[0: 3] = Base_pose[0]          # retrieve the orientation of Base as [Base_α, Base_β, Base_γ]

        Base_position = [vrep.simxGetObjectPosition(self.clientID, self.handles['base'][0],
                                                    -1, vrep.simx_opmode_blocking)[1]]
        state[3: 6] = Base_position[0]     # retrieve the position of Base as [Base_x, Base_y, Base_z]

        _, Base_Vel, Base_Ang_Vel = vrep.simxGetObjectVelocity(self.clientID, self.handles['base'][0],
                                                               vrep.simx_opmode_blocking)
        state[6: 9] = Base_Vel        # retrieve the linear velocity of Base as [Vx, Vy, Vz]
        state[9: 12] = Base_Ang_Vel
        state_visual = [vrep.simxGetVisionSensorImage(self.clientID, self.handles['sensors'][0],0,
                                                    vrep.simx_opmode_blocking)[2]]
        visual = np.asarray(state_visual)                   
        visual.shape = (1024,1024,3)
        visual=visual.astype(np.float)
        visual[visual < 0] += 255
        visual=np.fliplr(visual)
        visual = visual.astype(np.uint8)
        
    
        state = np.asarray(state)

        return state,visual

    def _set_joint_effort(self, U):         # set torque U = [u1, u2, u3] to 3 joints in V-REP
        
        _ = vrep.simxSetFloatSignal(self.clientID, 'u1',
                                       U[0], vrep.simx_opmode_oneshot)
        _ = vrep.simxSetFloatSignal(self.clientID, 'u2',
                                       U[1], vrep.simx_opmode_oneshot)
        
        _ = vrep.simxSetFloatSignal(self.clientID, 'u3',
                                       U[2], vrep.simx_opmode_oneshot)
        _ = vrep.simxSetFloatSignal(self.clientID, 'u4',
                                       U[3], vrep.simx_opmode_oneshot)
        
        
            
           
    def _reward(self, U):       # get the current reward
        # TODO: define the immediate reward function
        # want to minimize the distance between EE_point and EE_target_position
        reward=0
        # TODO: define the function for judging whether the simulation should be stopped.
        terminal_flag = False
       
        # TODO: define the function to specify the env information.
        env_info = {}

        return reward, terminal_flag, env_info
    def goal(self):
        goal_state = np.zeros(self.goal_dims)
        
        goal_state = np.asarray(goal_state)
        return goal_state
        
    def reset(self):        # reset the env
        if self.num_episode != 1:
            self.close()
            print('Episode Ended ...')

        self._init_vrep()
        self._get_handles()
        self._configure_initial_state()
        vrep.simxStartSimulation(self.clientID, vrep.simx_opmode_blocking)
        print('_________________________ Start Episode %d _________________________' % self.num_episode)
        self.t = 1
        self.num_episode += 1
        self.cur_obs,visual = self._get_observation()    # get current observation s_t

        return self.cur_obs,visual

    def step(self, action):      # execute one step in env
        self._set_joint_effort(action)

        # send a synchronization trigger signal to inform V-REP to execute the next simulation step
        vrep.simxSynchronousTrigger(self.clientID)
        vrep.simxGetPingTime(self.clientID)

        Reward, ter_flag, env_info = self._reward(action)     # ter_flag: True if finish the task

        # TODO: define the scaled reward
        
        self.t += 1

        next_observation,visual = self._get_observation()
        self.cur_obs = next_observation

        return next_observation,visual, Reward, ter_flag, env_info
    def compute_reward(self,state,action,goal):
        reward=0
        # TODO: define the function for judging whether the simulation should be stopped.
        terminal_flag = False
        

        # TODO: define the function to specify the env information.
    

        return reward, terminal_flag
        
    def close(self):        # end simulation
        vrep.simxStopSimulation(self.clientID, vrep.simx_opmode_blocking)
        vrep.simxGetPingTime(self.clientID)
        vrep.simxFinish(self.clientID)
