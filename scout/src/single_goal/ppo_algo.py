import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import os

GAMMA = 0.9
A_UPDATE_STEPS = 10
C_UPDATE_STEPS = 10
S_DIM, A_DIM = 5, 2
METHOD = [
    dict(name='kl_pen', kl_target=0.01, lam=0.5),   # KL penalty
    dict(name='clip', epsilon=0.2),                 # Clipped surrogate objective, find this is better
][1]        # choose the method for optimization

class ppo(object):

    def __init__(self):
        self.sess = tf.compat.v1.Session
        self.tfs = tf.compat.v1.placeholder(tf.float32, [None, S_DIM], 'state')
        
        # self.A_LR = 1e-7
        # self.C_LR = 2e-7
        
        self.C_LR = pow(10, np.random.uniform(-4, -9))
        self.A_LR = np.random.rand() * self.C_LR

        # critic
        with tf.compat.v1.variable_scope('critic'):
            l1 = tf.keras.layers.Dense(self.tfs, 100, tf.nn.relu)
            self.v = tf.keras.layers.Dense(l1, 1)
            self.tfdc_r = tf.compat.v1.placeholder(tf.float32, [None, 1], 'discounted_r')
            self.advantage = self.tfdc_r - self.v
            self.closs = tf.reduce_mean(tf.square(self.advantage))
            self.ctrain_op = tf.compat.v1.train.AdamOptimizer(self.C_LR).minimize(self.closs)

        # actor
        pi, pi_params = self._build_anet('pi', trainable=True)
        oldpi, oldpi_params = self._build_anet('oldpi', trainable=False)

        with tf.compat.v1.variable_scope('sample_action'):
            self.sample_op = tf.squeeze(pi.sample(1), axis=0)       # choosing action
        with tf.compat.v1.variable_scope('update_oldpi'):
            self.update_oldpi_op = [oldp.assign(p) for p, oldp in zip(pi_params, oldpi_params)]

        self.tfa = tf.compat.v1.placeholder(tf.float32, [None, A_DIM], 'action')
        self.tfadv = tf.compat.v1.placeholder(tf.float32, [None, 1], 'advantage')

        with tf.compat.v1.variable_scope('loss'):
            with tf.compat.v1.variable_scope('surrogate'):
                ratio = pi.prob(self.tfa) / oldpi.prob(self.tfa)
                surr = ratio * self.tfadv

            self.aloss = -tf.reduce_mean(tf.minimum(
                surr,
                tf.clip_by_value(ratio, 1.-METHOD['epsilon'], 1.+METHOD['epsilon'])*self.tfadv))

        with tf.compat.v1.variable_scope('atrain'):
            self.atrain_op = tf.compat.v1.train.AdamOptimizer(self.A_LR).minimize(self.aloss)

        tf.compat.v1.summary.FileWriter("/home/xyw/BUAA/Graduation/src/scout/result/log/", self.sess.graph_def)
        self.sess.run(tf.compat.v1.global_variables_initializer())

    def update(self, s, a, r):
        self.sess.run(self.update_oldpi_op)
        adv = self.sess.run(self.advantage, {self.tfs: s, self.tfdc_r: r})
        
        # update actor
        [self.sess.run(self.atrain_op, {self.tfs: s, self.tfa: a, self.tfadv: adv}) for _ in range(A_UPDATE_STEPS)]

        # update critic
        [self.sess.run(self.ctrain_op, {self.tfs: s, self.tfdc_r: r}) for _ in range(C_UPDATE_STEPS)]

    def _build_anet(self, name, trainable):
        with tf.compat.v1.variable_scope(name):
            l1 = tf.keras.layers.Dense(self.tfs, 100, tf.nn.relu, trainable=trainable)
            mu = 2 * tf.keras.layers.Dense(l1, A_DIM, tf.nn.tanh, trainable=trainable)
            sigma = tf.keras.layers.Dense(l1, A_DIM, tf.nn.softplus, trainable=trainable)
            norm_dist = tf.distributions.Normal(loc=mu, scale=sigma)   
        params = tf.compat.v1.get_collection(tf.compat.v1.GraphKeys.GLOBAL_VARIABLES, scope=name)
        return norm_dist, params

    def choose_action(self, s):
        s = s[np.newaxis, :]    
        a = self.sess.run(self.sample_op, {self.tfs: s})[0]
        return a

    def get_v(self, s):
        if s.ndim < 2: s = s[np.newaxis, :]
        return self.sess.run(self.v, {self.tfs: s})[0, 0]
    
    def save(self, TRAIN_TIME):
        dir_path = '/home/xyw/Train_Result/single/model/PPO_%i.ckpt' %(TRAIN_TIME)
        saver = tf.compat.v1.train.Saver()
        saver.save(self.sess, dir_path)
    
    def restore(self, TRAIN_TIME):
        model_path = '/home/xyw/Train_Result/single/model/PPO_%i.ckpt' %(TRAIN_TIME)
        if os.path.exists(model_path):
            restorer = tf.compat.v1.train.import_meta_graph(model_path+'.meta')
            restorer.restore(self.sess, tf.train.latest_checkpoint(model_path))
        else:
            print('No pre-trained model exist')

    def resetgraph(self):
        tf.compat.v1.reset_default_graph()
