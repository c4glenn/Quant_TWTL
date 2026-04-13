# Copyright (c) 2024 Ahmad Ahmad <ahmadgh@bu.edu>, Cristian-Ioan Vasile <cvasile@lehigh.edu>
# SPDX-License-Identifier: MIT
from twtl_ast import RelOperation
from twtl import Trace, predicate_normalized_value


class AP(object):
    '''An atomic proposition defined as a linear predicate h(x) rel threshold.

    Parameters
    ----------
    h        : callable | None  — function h(state) → float (typically linear)
    inst_rho : float | None     — instantaneous robustness value, cached here
    L        : callable | None  — labeling function L(observation) → bool
    '''

    def __init__(self, h=None, inst_rho=None, L=None):
        self.h        = h         # h-function over observed states
        self.inst_rho = inst_rho  # instantaneous robustness
        self.L        = L         # labeling function over observations

    def get_h_value(self, t=None, ot=None, o_traj=None):
        '''Evaluates h at the given observation.

        Parameters
        ----------
        t      : float — time index
        ot     : array — single observation at time t
        o_traj : array — full observation trajectory
        '''
        if self.h is not None and ot is not None:
            return self.h(ot)
        return None
