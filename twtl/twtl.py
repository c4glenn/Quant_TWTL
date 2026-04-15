# Copyright (c) 2024 Ahmad Ahmad <ahmadgh@bu.edu>, Cristian-Ioan Vasile <cvasile@lehigh.edu>
# SPDX-License-Identifier: MIT
'''
.. module:: twtl.py
   :synopsis: TWTL monitoring, robustness, and DFA translation API.

.. moduleauthor:: Cristian Ioan Vasile <cvasile@bu.edu>
.. moduleauthor:: Ahmad Ahmad <ahmadgh@bu.edu>
'''

import logging
import itertools as it

import numpy as np
import scipy
from scipy.interpolate import interp1d
from antlr4 import InputStream, CommonTokenStream

from .twtlLexer import twtlLexer
from .twtlParser import twtlParser
from .twtl_ast import TWTLAbstractSyntaxTreeExtractor, to_ast
from .twtl_ast import Operation as Op
from .twtl_ast import RelOperation
from .dfa import setDFAType, DFAType, setOptimizationFlag
# from ordered_set import OrderedSet as oset
import copy



def monitor(formula=None, kind=None, dfa=None, cutoff=None):
    '''Creates a monitor for a TWTL formula.
    It accept the following combinations of parameters:
    1) a formula and its kind;
    2) a dfa, in which case kind is silently ignored.
    In either case a dfa is available for monitoring.
    The cutoff parameter limits the maximum range a trajectory is monitored.
    If it is absent, then the cutoff horizon is the formula upper norm or
    infinite for the normal and infinity versions of the TWTL formula,
    respectively.
    '''
    # either compute infinity automaton or use the one provided
    if formula is None and dfa is None:
        raise Exception('Must provide either a TWTL formula or an automaton!')
    elif dfa is None:
        _, dfa = translate(formula, kind=kind)
    kind = dfa.kind

    if  kind == DFAType.Normal:
        if formula is not None:
            seq = range((norm(formula) if cutoff is None else cutoff) + 1)
        else:
            seq = range(cutoff + 1)
    elif kind == DFAType.Infinity:
        seq = it.count() if cutoff is None else xrange(cutoff + 1)
    else:
        raise ValueError('DFA type must be either DFAType.Normal, ' +
                       'DFAType.Infinity or "both"! {} was given!'.format(kind))

    state = dfa.init.keys()[0]
    ret = 0
    for _ in seq:
        symbol = yield ret
        r = dfa.next_states_of_fsa(state, symbol)
        assert len(r) <= 1, 'Should be deterministic!'
        if r:
            state = r[0]
            ret = 1*(state in dfa.final)
        else:
            break
    while True:
        yield -1

def _init_tree(tree):
    '''Initialized the tree for computing the temporal relaxations.'''
    stack = [tree]
    while stack:
        t = stack.pop()
        if t.operation == Op.event:
            t.active = False
            t.done = False
            t.tau = -1
        if t.left is not None:
            stack.append(t.left)
        if t.right is not None:
            stack.append(t.right)

def _update_tree(tree, state, prev_state, symbol, constraint=None):
    '''Updated the activity and tau values of all eventually operators based on
    the current state, the previous state and the previous symbol. The
    ``constraints'' parameter is used to choose which part of the formula is
    considered when evaluating disjunction operators.
    '''
    if tree.unr:
        return
    if tree.operation == Op.event:
        if state in tree.init:
            tree.active = True
        if state in tree.final:
            if constraint is None:
                tree.active = False
                tree.done = True
            elif set([symbol]) <= constraint.get(prev_state, set()):
                tree.active = False
                tree.done = True
        if tree.active:
            tree.tau += 1
        if not tree.wwf:
            _update_tree(tree.left, state, prev_state, symbol, constraint)
    elif tree.operation == Op.CONCAT:
        _update_tree(tree.left, state, prev_state, symbol)
        _update_tree(tree.right, state, prev_state, symbol, constraint)
    elif tree.operation == Op.AND:
        _update_tree(tree.left, state, prev_state, symbol, constraint)
        _update_tree(tree.right, state, prev_state, symbol, constraint)
    elif tree.operation == Op.OR:
        if constraint is None:
            c_left = {s: ch.both | ch.left for s, ch in tree.choices.iteritems()}
            c_right = {s: ch.both | ch.right for s, ch in tree.choices.iteritems()}
        else:
            c_left = dict()
            c_right = dict()
            for s in tree.choices.viewkeys() & constraint.viewkeys():
                c_left[s] = constraint[s] & (tree.choices[s].both | tree.choices[s].left)
                c_right[s] = constraint[s] & (tree.choices[s].both | tree.choices[s].right)
        _update_tree(tree.left, state, prev_state, symbol, c_left)
        _update_tree(tree.right, state, prev_state, symbol, c_right)

def _eval_relaxation(tree):
    '''Evaluates the tau values and returns the maximum deadline and the
    associated valuation of all the tau values.
    '''
    if tree.unr:
        return float('-Inf'), []
    if tree.wwf and tree.operation == Op.event:
        if not tree.done:
            tree.tau = float('-Inf')
        else:
            tree.tau -= tree.high
        return tree.tau, [(tree.tau, (tree.low, tree.high))]
    if not tree.wwf and tree.operation == Op.event:
        t_opt_left, tau_left = _eval_relaxation(tree.left)
        if not tree.done:
            tree.tau = float('-Inf')
            return tree.tau, tau_left + [(tree.tau, (tree.low, tree.high))]
        else:
            tree.tau -= tree.high
            return max(tree.tau, t_opt_left), tau_left + [(tree.tau, (tree.low, tree.high))]
    if tree.operation in (Op.CONCAT, Op.AND, Op.OR):
        t_opt_left, tau_left = _eval_relaxation(tree.left)
        t_opt_right, tau_right = _eval_relaxation(tree.right)
        if tree.operation in (Op.CONCAT, Op.AND):
            if t_opt_left > float('-Inf') and t_opt_left > float('-Inf'):
                return max(t_opt_left, t_opt_right), tau_left + tau_right
            else:
                return float('-Inf'), tau_left + tau_right
        else:
            if t_opt_left > float('-Inf') and t_opt_left > float('-Inf'):
                return min(t_opt_left, t_opt_right), tau_left + tau_right
            else:
                return max(t_opt_left, t_opt_right), tau_left + tau_right

def temporal_relaxation(word, formula=None, dfa=None):
    '''Computes the temporal relaxation of the given formula or dfa such that
    the given word satisfies the formula or is accepted by the automaton,
    respectively.
    Note: If an automaton is specified, it must not be optimized.
    '''
    # either compute infinity automaton or use the one provided
    if formula is None and dfa is None:
            raise Exception('Must provide either a TWTL formula or'
                            + ' an infinity automaton!')
    elif dfa is None:
        _, dfa = translate(formula, kind=DFAType.Infinity, optimize=False)
    assert dfa.kind == DFAType.Infinity

    # initialize tree
    _init_tree(dfa.tree)
#     logging.debug('Init:\n%s', _debug_pprint_tree(dfa.tree))

    prev_state = None
    state = dfa.init.keys()[0]
    prev_w = set()
    for w in word + [set([])]: # hack to catch the last state
        # start/stop counters and increment all active counters
        _update_tree(dfa.tree, state, prev_state, dfa.bitmap_of_props(prev_w))
#         logging.debug('Update: state=%s prev_state=%s w=%s prev_w=%s final=%s',
#                       state, prev_state, w, prev_w, dfa.final)
#         logging.debug('Update:\n%s', _debug_pprint_tree(dfa.tree))
        # test for satisfaction
        if state in dfa.final:
            break
        else: # compute next state
            r = dfa.next_states(state, w)
            assert len(r) == 1, 'Should be deterministic!'
            prev_state = state
            state = r[0]
        prev_w = w
    # substract deadlines from counter values to obtain the tau values
    return _eval_relaxation(dfa.tree)

def norm(formula: str):
    '''Returns the (lower, upper) time bounds of the TWTL formula string.

    Parameters
    ----------
    formula : str
        TWTL formula string.

    Returns
    -------
    list[int, int]
        [lower_bound, upper_bound]
    '''
    return to_ast(formula).robustness_time_bounds()

def translate(ast, kind='both', norm=False, optimize=True):
    '''Converts a TWTL formula into an FSA. It can returns both a normal FSA or
    the automaton corresponding to the relaxed infinity version of the
    specification.
    If kind is: (a) DFAType.Normal it returns only the normal version;
    (b) DFAType.Infinity it returns only the relaxed version; and
    (c) 'both' it returns both automata versions.
    If norm is True then the bounds of the TWTL formula are computed as well.

    The functions returns a tuple containing in order: (a) the alphabet;
    (b) the normal automaton (if requested); (c) the infinity version automaton
    (if requested); and (d) the bounds of the TWTL formula (if requested).

    The ``optimize'' flag is used to specify that the annotation data should be
    optimized. Note that the synthesis algorithm assumes an optimized automaton,
    while computing temporal relaxations is performed using an unoptimized
    automaton.
    '''
    if kind == 'both':
        kind = [DFAType.Normal, DFAType.Infinity]
    elif kind in [DFAType.Normal, DFAType.Infinity]:
        kind = [kind]
    else:
        raise ValueError('DFA type must be either DFAType.Normal, ' +
                         'DFAType.Infinity or "both"! {} was given!'.format(kind))

    # lexer = twtlLexer(InputStream(formula))
    # tokens = CommonTokenStream(lexer)
    # parser = twtlParser(tokens)
    # phi = parser.formula()

    # # AST
    # ast = TWTLAbstractSyntaxTreeExtractor().visit(t)
    

    alphabet = ast.propositions(set())# oset([]))  # set of predicates / propositions
    result = [alphabet]


    if DFAType.Normal in kind:
        setDFAType(DFAType.Normal)
        dfa = twtl2dfa(formula_ast=ast,props=alphabet)
        dfa.kind = DFAType.Normal
        result.append(dfa)

    if DFAType.Infinity in kind:
        setDFAType(DFAType.Infinity)
        setOptimizationFlag(optimize)
        dfa_inf = twtl2dfa(ast, alphabet)
        dfa_inf.kind = DFAType.Infinity
        result.append(dfa_inf)

    if norm: # compute TWTL bound
        result.append(ast.bounds())

    if logging.getLogger().isEnabledFor(logging.DEBUG):
        for mode, name in [(DFAType.Normal, 'Normal'),
                           (DFAType.Infinity, 'Infinity')]:
            if mode not in kind:
                continue
            elif mode == DFAType.Normal:
                pdfa = dfa
            else:
                pdfa = dfa_inf
            logging.debug('[spec] spec: {}'.format(formula))
            logging.debug('[spec] mode: {} DFA: {}'.format(name, pdfa))
            if mode == DFAType.Infinity:
                logging.debug('[spec] tree:\n{}'.format(pdfa.tree.pprint()))
            logging.debug('[spec] No of nodes: {}'.format(pdfa.g.number_of_nodes()))
            logging.debug('[spec] No of edges: {}'.format(pdfa.g.number_of_edges()))

    return tuple(result)


# AGM robustness: Methods and monitoring: 
def powermean(vector, order, plus=0, lmda = 1, k = 1):
    '''Computes the power mean of a vector.
    
    Special cases: 
    If order > 0; returns the arithmetic mean
    If order ==0; returns the geometric mean

    lmda: weighting parameter for the concatenation operator. 
    k   : power for the lmda parameter 

    '''
    alpha = 1. / len(vector)
    if order == 'inf':
        return np.max(vector)
    elif order == '-inf':
        return np.min(vector)
    if order != 0:
        if plus:
            return np.sum(alpha * (1+abs(vector))**order)**(1./order) - 1
        else:
            return np.sum((lmda**k) * alpha * abs(vector)**order)**(1./order)
    else:
        if plus:
            return np.prod(1 + abs(vector)) ** alpha - 1
        else:
            return np.prod(abs(vector)) ** alpha

def conjunction_function(r_children, pos_order, neg_order, plus=0,lmda = 1 , k = 1):
    '''Computes the conjuction robustness value from children values.
    neg_order:
    pos_order:  
    '''
    r_non_pos = r_children <= 0
    if np.any(r_non_pos):
        # eta = powermean(-r_children * r_non_pos, order=neg_order, plus=plus,lmda = lmda, k = k)
        # (The original code of Cristi)
        eta = -powermean(-r_children * r_non_pos, order=neg_order, plus=plus,lmda = lmda, k = k) # Done TODO [sci] Why - ???? Check the original AGM paper and compare it with yours
    else:
        eta = powermean(r_children, order=pos_order, plus=1, lmda = lmda, k = k) # Done!
    return eta

def disjunction_function(r_children, pos_order, neg_order, plus=0,lmda = 1, k = 1):
    '''Computes the disjuction robustness value from children values.
    Note: Returns the same value as:
        -conjunction_function(-r_children, pos_order, neg_order, plus)
    '''
    r_pos = r_children > 0
    if np.any(r_pos):
        eta = powermean(r_children * r_pos, order=neg_order, plus=plus,lmda = lmda, k = k) # Must arithmetic mean
    else:
        eta = -powermean(-r_children, order=pos_order, plus=plus,lmda = lmda, k = k)        # Must be Gmtrc Mean --+1
    return eta

def agm_robustness(formula, times ,trace = None, t1=None,t2=None,pos_order=0, neg_order=1,
                         maximum_robustness=1, plus=0, dt = .1):
    '''Computes the powermean robustness of the STL formula.'''
    #+ 
    assert trace is not None
    
    # if formula.relation is not None: #TODO [right after] How to normalize the predicates? Include the range of each variable in the - Trace; - AST; - Else 
    #     # This is essentially the linear predicate valuations 
    #     return eta 
    if formula.op == Op.NOP: #Predicated proposition 
        pass
    elif formula.op == Op.PRED:
        value = trace.value(formula.variable, times)
        if formula.relation in (RelOperation.GT, RelOperation.GE):
            eta = value - formula.threshold
        elif formula.relation in (RelOperation.LT, RelOperation.LE):
            eta = formula.threshold - value
        elif formula.relation == RelOperation.EQ:
            eta = -abs(value - formula.threshold)
        elif formula.relation == RelOperation.NQ:
            eta = abs(value - formula.threshold)
        return eta / trace.range(formula.variable) # normalization
    
    elif formula.op == Op.HOLD:
        d = formula.duration
        if len(times)==0:
            return -1 
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        times = [t for t in times if t1 <= t <= (d*dt)+t1]
        if (t2 - t1)+dt < (d*dt):
            eta = -1 
        else: 
            # traj = trace.value(formula.variable,times[0:-1])
            if formula.nf_subformula is not None: # A conjunction of predicates: 
                nf_subformula = formula.nf_subformula
                if not (nf_subformula.op in (Op.AND, Op.OR)): 
                    raise('No NF subformula is given.')
                # Compute eta at each time instance: 
                 # At each time instance we'll compute the AGM for a conjunctive formula: 
                etas = np.array([agm_robustness(formula = nf_subformula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # after these being computed, search if any violates the specs and compute the A or G robustness
                eta = conjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)
                
                # TODO [right after] code conjunction "function" and disjunction "function", given that m = len(times) 
            else: # If the child is a singleton (a linear predicate).  
                predFormula = copy.copy(formula)
                predFormula.op = Op.PRED
                etas = np.array([agm_robustness(formula = predFormula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # FIXME the predicate should be a child of the holdFormula
                eta = conjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)
        return eta
    elif formula.op == Op.WITHIN:
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
            
        if len(times)==0 or t2 - t1 < formula.high: # For soundness, intuitively, we need long enough traces of the system  
            return -1
        else:
            times = [t for t in times if t1+formula.low <= t <= t1+formula.high]
            etas = np.array([agm_robustness(formula = formula.child, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                  for tau in times],dtype=np.float64)
            eta = disjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)
        return eta
    
    elif formula.op in (Op.OR,Op.AND):
        # raise('need debugging')
        # times = [t]
        etas = np.array([agm_robustness(formula=child, trace=trace, times=times,dt=dt)
                        for child in [formula.left, formula.right]],dtype=np.float64)
        if formula.op == Op.OR: 
            eta = disjunction_function(etas, pos_order, neg_order, plus=plus)
        else: 
            eta = conjunction_function(etas, pos_order, neg_order, plus=plus)
        return eta
    elif formula.op == Op.NOT: 
        raise('not implemented')
    elif formula.op == Op.CONCAT:
        reduced_com_flag = False
        times = list(times)
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        true_time1 = np.array(times) >= formula.left.bounds_vls[0]
        true_time2 = np.array(times) < t2-formula.right.bounds_vls[0]
        if False: #not np.any(np.logical_and(true_time1,true_time2)):
            etas_1 = np.array([agm_robustness(formula = formula.left, trace=trace,
                                          times = times[np.where(np.logical_and(times>=t1,times<=tau))]
                                          ,dt=dt) for tau in times if tau >= formula.left.bounds_vls[0]])
            if len(etas_1)==0:  
                etas_1 = -1
            # The completion for the 2nd subformula
            etas_2 = np.repeat(-1,len(etas_1))
            etas_con = np.array([conjunction_function(r_children = np.array([etas_1[i],etas_2[i]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(etas_1.shape[0])])
            eta = disjunction_function(r_children = etas_con,pos_order = pos_order, neg_order = neg_order, plus=plus)
            return eta
        if reduced_com_flag:
            # times_subf1 = times[np.where(np.logical_and(times>=t1,times<=formula.left.bounds_vls[0]))]
            # times_subf2 = times[np.where(np.logical_and(times>=formula.left.bounds_vls[0]+dt,times<=t2))]
            # etas = np.array([agm_robustness(formula = formula.left, trace=trace,times =  
            #                                         times_subf1,dt=dt),
            #                 agm_robustness(formula = formula.right, trace=trace,times =  
            #                                         times_subf2,dt=dt)])
            etas = np.array([(agm_robustness(formula = formula.left, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=t1,times<=tau))],dt=dt),
                            agm_robustness(formula = formula.right, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=tau+dt,times<=t2))],dt=dt)) 
                                                    for tau in times if tau >= formula.left.bounds_vls[0] and tau < t2-formula.right.bounds_vls[0]],dtype=np.float64)
        else:
            # >>>> The robustness with extra computation: 
            etas = np.array([(agm_robustness(formula = formula.left, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=t1,times<=tau))],dt=dt),
                            agm_robustness(formula = formula.right, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=tau+dt,times<=t2))],dt=dt)) 
                                                    for tau in times[0:-1]],dtype=np.float64)
            if len(etas)==0: 
                return -1
        etas_con = np.array([conjunction_function(r_children = np.array([etas[i,0],etas[i,1]]),\
                      pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(etas.shape[0])])
        eta = disjunction_function(r_children = etas_con,pos_order = pos_order, neg_order = neg_order, plus=plus)
        return eta
    else: 
        raise('You are not accounting for op:%d',formula.op)

def monitor_agm(formula, times ,trace = None, t1=None,t2=None, pos_order=0, neg_order=1,
                         maximum_robustness=1, plus=0,dt = 0.1):
    '''
    
    Input/parameters: 
    formula: The abstract syntax tree of the formula, 
    times: The time trajectory of the given partial signal 
    trace: The trace of the system, (will be truncated based on times)
    t1:        The initial time stamp of the times, 
    t2:        The final time stamp of times

    Outputs: 
    [ueta, leta]: AGM robustness interval, an interval semantics for the true AGM robustness given partial run of the system

    '''
    assert trace is not None
    if formula.op == Op.NOP: #Predicated proposition 
        pass
    elif formula.op == Op.PRED: 
        value = trace.value(formula.variable, times)  # FIXME make sure that the correct time step is used wrt the fed signal 
        if formula.relation in (RelOperation.GT, RelOperation.GE):
            eta = value - formula.threshold
        elif formula.relation in (RelOperation.LT, RelOperation.LE):
            eta = formula.threshold - value
        elif formula.relation == RelOperation.EQ:
            eta = -abs(value - formula.threshold)
        elif formula.relation == RelOperation.NQ:
            eta = abs(value - formula.threshold)
        ueta = eta / trace.range(formula.variable) # normalization
        return [ueta,ueta]
    
    elif formula.op == Op.HOLD:
        # >>> Assigning the max and min etas as -+1. For the Lipschitz monitoring, though,  we need to compute them online 
        eta_min, eta_max = -1.,1.
        # <<<
        d = formula.duration
        if len(times)==0:
            return -1 
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        times = [t for t in times if t1 <= t <= (d*dt)+t1]
        
        
        if (t2 - t1)+dt < (d*dt): # Partial trajectory for the H operator: 
            # dt = times[1]-times[0]
            n_cmpln_stamps = int(((d*dt) - (times[-1]-times[0]))/dt)-1 # Make sure to instantiate with eta max
            n_stamps = int((d)/dt)
            # >>> Assigned the min/max values; for the Lipschitz monitoring, though, every value need to be computed. 
            etas_min , etas_max = np.repeat(eta_min,n_cmpln_stamps), np.repeat(eta_max,n_cmpln_stamps)
            # <<< 
            if formula.nf_subformula is not None: # A conjunction of predicates: 
                nf_subformula = formula.nf_subformula
                if not (nf_subformula.op in (Op.AND, Op.OR)): 
                    raise('No NF subformula is given.')
                # Compute eta at each time instance: 
                    # At each time instance we'll compute the AGM for a conjunctive formula: 
                etas = np.array([agm_robustness(formula = nf_subformula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # after these being computed, search if any violates the specs and compute the A or G robustness
                pos_etas = etas < 0 
                if np.any(pos_etas): # If any point has already violated the specs: 
                    etas_u = np.concatenate((etas,etas_max))
                    etas_l = np.concatenate((etas,etas_min))
                    ueta = conjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    leta = conjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
                else:     
                    etas = np.concatenate((etas,etas_max))
                    # ueta = eta = conjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)  
                    ueta = conjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)  
                    leta = (n_cmpln_stamps/n_stamps) * eta_min 
                return [leta,ueta]    
                # TODO [right after] code conjunction "function" and disjunction "function", given that m = len(times) 
            else: # If the child is a singleton (a linear predicate).  
                predFormula = copy.copy(formula)
                predFormula.op = Op.PRED
                etas = np.array([agm_robustness(formula = predFormula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # FIXME the predicate should be a child of the holdFormula
                neg_etas = etas < 0 
                if np.any(neg_etas): # If any point has already violated the specs: 
                    etas_u = np.concatenate((etas,etas_max))
                    etas_l = np.concatenate((etas,etas_min))
                    # Cristi's Code ueta = conjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    # Cristi's Code leta = conjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    ueta = conjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    leta = conjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
                else:     
                    etas = np.concatenate((etas,etas_max))
                    ueta = conjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)  
                    leta = (n_cmpln_stamps/n_stamps) * eta_min 
                return [leta,ueta]    
        else: #Completed trajectory   
            leta = agm_robustness(formula = formula, trace=trace,times = times,dt=dt)
            return [leta,leta]
    elif formula.op == Op.WITHIN:
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
          
        if len(times)==0 or t2 - t1 < formula.high: # For soundness, intuitively, we need long enough traces of the system  
            times = [t for t in times if t1+formula.low <= t <= t2]
            n_cmpln_stamps = int((formula.high - (times[-1]-times[0]))/dt)
            etas_min , etas_max = np.repeat(-1,n_cmpln_stamps), np.repeat(1,n_cmpln_stamps)
            rosis = np.array([monitor_agm(formula = formula.child, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                  for tau in times],dtype=np.float64)
            etas_l, etas_u = np.concatenate((rosis[:,0],etas_min)),np.concatenate((rosis[:,1],etas_max))
            ueta = disjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
            leta = disjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
            return [leta,ueta]
            # Do AGM upon the returned rosis: 
        else:
            times = [t for t in times if t1+formula.low <= t <= t2] # Recall that t2 < t1+formula.high
            etas = np.array([agm_robustness(formula = formula.child, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                  for tau in times if np.any(np.logical_and(times>=tau,times<=t1+formula.high))],dtype=np.float64)
            # times_ = [times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))] 
            #                     for tau in times[0:-1] if not np.any(np.logical_and(times>=tau,times<=t1+formula.high))>0]
            a = 1
            leta = disjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)
            return [leta,leta]
        
    elif formula.op in (Op.AND, Op.OR):
        rosis = np.array([monitor_agm(formula=child, trace=trace, times=times,dt = dt)
                        for child in [formula.left, formula.right]],dtype=np.float64)
        etas_l, etas_u = rosis[:,0], rosis[:,1]
        if formula.op == Op.OR: 
            ueta = disjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
            leta = disjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
        else: 
            ueta = conjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
            leta = conjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
        return [leta,ueta]
    elif formula.op == Op.CONCAT: 
        eta_min = -1
        eta_max = 1 
        times = list(times)
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        # dt = times[1] - times[0]
        true_time1 = np.array(times) >= formula.left.bounds_vls[0]
        true_time2 = np.array(times) < t2-formula.right.bounds_vls[0]
        if not np.any(np.logical_and(true_time1,true_time2)):
            rosis_1 = np.array([monitor_agm(formula = formula.left, trace=trace,
                                          times = times[np.where(np.logical_and(times>=t1,times<=tau))]
                                          ,dt=dt) for tau in times])
            # The completion for the 2nd subformula
            etas_min , etas_max = np.repeat(eta_min,len(rosis_1[:,0])), np.repeat(eta_max,len(rosis_1[:,0]))
            rosis_conl = np.array([conjunction_function(r_children = np.array([rosis_1[i,0],etas_min[i]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(rosis_1.shape[0])])
            rosis_conu = np.array([conjunction_function(r_children = np.array([rosis_1[i,1],etas_max[i]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(rosis_1.shape[0])])
            rosi = [disjunction_function(r_children = rosis_conl,pos_order = pos_order, neg_order = neg_order, plus=plus),\
                    disjunction_function(r_children = rosis_conu,pos_order = pos_order, neg_order = neg_order, plus=plus)]
            return rosi
        else:    
            rosis_t = np.array([(monitor_agm(formula = formula.left, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=t1,times<=tau))],dt=dt),
                            monitor_agm(formula = formula.right, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=tau+dt,times<=t2))],dt=dt)) \
                                                        for tau in times if 
                                                        tau >= formula.left.bounds_vls[0] and tau < t2-formula.right.bounds_vls[0]],dtype=np.float64)
            
            rosis_conl = np.array([conjunction_function(r_children = np.array([rosis_t[i,0,0],rosis_t[i,1,0]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(rosis_t.shape[0])])
            rosis_conu = np.array([conjunction_function(r_children = np.array([rosis_t[i,0,1],rosis_t[i,1,1]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(rosis_t.shape[0])])
            rosi = [disjunction_function(r_children = rosis_conl,pos_order = pos_order, neg_order = neg_order, plus=plus),\
                    disjunction_function(r_children = rosis_conu,pos_order = pos_order, neg_order = neg_order, plus=plus)]
            return rosi
    else: 
        raise('the provided operator is not implementable')
 
# >>>>>> Developing the monitoring at realtime using a sliding maximum-like algorithm: 
def monitor_agm_rt(formula, times ,trace = None, t1=None,t2=None,tp_end=0, pos_order=0, neg_order=1,
                         maximum_robustness=1, plus=0,dt = 0.1, rosi_in = None,rosi_prev = None, rt_mntrg_flg = True,ts = 0):
    '''
    
    Input/parameters: 
    formula: The abstract syntax tree of the formula, 
    times: The time trajectory of the given partial signal 
    trace: The trace of the system, (will be truncated based on times)
    t1:        The initial time stamp of the times, 
    t2:        The final time stamp of times
    ts:        The initial time of the history. 

    Outputs: 
    [ueta, leta]: AGM robustness interval, an interval semantics for the true AGM robustness given partial run of the system

    '''
    assert trace is not None
    eta_max = 1.0 
    eta_min = -1.0 
    
    
    if formula.op == Op.NOP: #Predicated proposition 
        pass
    elif formula.op == Op.PRED:
        value = trace.value(formula.variable, times)
        rng = trace.range(formula.variable)
        ueta = predicate_normalized_value(value=value,threshold=formula.threshold,relation=formula.relation,rng=rng)
        # if formula.relation in (RelOperation.GT, RelOperation.GE):
        #     eta = value - formula.threshold
        # elif formula.relation in (RelOperation.LT, RelOperation.LE):
        #     eta = formula.threshold - value
        # elif formula.relation == RelOperation.EQ:
        #     eta = -abs(value - formula.threshold)
        # elif formula.relation == RelOperation.NQ:
        #     eta = abs(value - formula.threshold)
        # ueta = eta / trace.range(formula.variable) # normalization
        return [ueta,ueta]
    
    elif formula.op == Op.HOLD:
        ##SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSINGELTON OBSERVATION >>
        ##SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSINGELTON OBSERVATION <<
        
        #PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPARTIAL SINGNAL OBSERVATON >>
        # >>> Assigning the max and min etas as -+1. For the Lipschitz monitoring, though,  we need to compute them online 
        eta_min, eta_max = -1.,1.
        # <<<
        d = formula.duration
        if len(times)==0:
            return -1 
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        times = [t for t in times if t1 <= t <= (d*dt)+t1]
        
        
        # ~~~ The cases with non-incremental monitoring: ~~~~
        if (t2 - t1)+dt < (d*dt) and (not rt_mntrg_flg or rosi_in is None): # Partial trajectory for the H operator: 
            # dt = times[1]-times[0]
            n_cmpln_stamps = int(((d*dt) - (times[-1]-times[0]))/dt)
            n_stamps = int((d)/dt)+1
            # >>> Assigned the min/max values; for the Lipschitz monitoring, though, every value need to be computed. 
            etas_min , etas_max = np.repeat(eta_min,n_cmpln_stamps), np.repeat(eta_max,n_cmpln_stamps)
            # <<< 
            if formula.nf_subformula is not None: # A conjunction of predicates: 
                nf_subformula = formula.nf_subformula
                if not (nf_subformula.op in (Op.AND, Op.OR)): 
                    raise('No NF subformula is given.')
                # Compute eta at each time instance: 
                    # At each time instance we'll compute the AGM for a conjunctive formula: 
                etas = np.array([agm_robustness(formula = nf_subformula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # after these being computed, search if any violates the specs and compute the A or G robustness
                pos_etas = etas < 0 
                if np.any(pos_etas): # If any point has already violated the specs: 
                    etas_u = np.concatenate((etas,etas_max))
                    etas_l = np.concatenate((etas,etas_min))
                    ueta = conjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    leta = conjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
                else:     
                    etas = np.concatenate((etas,etas_max))
                    ueta = eta = conjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)  
                    leta = (n_cmpln_stamps/n_stamps) * eta_min 
                return [leta,ueta]    
                # TODO [right after] code conjunction "function" and disjunction "function", given that m = len(times) 
            else: # If the child is a singleton (a linear predicate).  
                predFormula = copy.copy(formula)
                predFormula.op = Op.PRED
                etas = np.array([agm_robustness(formula = predFormula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # FIXME the predicate should be a child of the holdFormula
                neg_etas = etas < 0 
                if np.any(neg_etas): # If any point has already violated the specs: 
                    etas_u = np.concatenate((etas,etas_max))
                    etas_l = np.concatenate((etas,etas_min))
                    ueta = conjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    leta = conjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
                else:     
                    etas = np.concatenate((etas,etas_max))
                    ueta = conjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)  
                    leta = (n_cmpln_stamps/n_stamps) * eta_min 
                return [leta,ueta]    
        elif  not rt_mntrg_flg or rosi_in is None: #Completed trajectory   
            # TODO Make sure to return the same rosi if we already have complete signals. 
            leta = agm_robustness(formula = formula, trace=trace,times = times,dt=dt)
            return [leta,leta]
        # ~~~ The cases with incremental monitoring: ~~~~
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        else: 
            
             # Case 0: ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            if rosi_in[0]==rosi_in[1]: # The case if I already have complete signals that satisfied the specs:
                return rosi_in
            #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            #compute rosi given the new subtraj:  
            n_cmpln_stamps = int(((d*dt) - (times[-1]-ts))/dt) # Number of completions given the original signal 
            n_completed    =  int(((d*dt) - (times[0]-ts+dt))/dt) # Number of points needed for completed signal given the new signal
            n_stamps = int((d)/dt)+1                      # Given the bound of TWTL formula
            if n_cmpln_stamps < 0:
                raise TypeError('not implemented')               
            if n_cmpln_stamps>0:
                # Will be just used in case: A2, B2 (or maybe not needed at all)
                etas_min , etas_max = np.repeat(eta_min,n_cmpln_stamps), np.repeat(eta_max,n_cmpln_stamps) 

            # The computation of eta for a predicate 
            if formula.nf_subformula is not None:
                nf_subformula = formula.nf_subformula
                if not (nf_subformula.op in (Op.AND, Op.OR)): 
                    raise('No NF subformula is given.')
                etas = np.array([agm_robustness(formula = nf_subformula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # after these being computed, search if any violates the specs and compute the A or G robustness
                # TODO [rt_dbgng] Make sure to include the needed points when computing the robustness intervals; 
            else: 
                predFormula = copy.copy(formula)
                predFormula.op = Op.PRED
                etas = np.array([agm_robustness(formula = predFormula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64)
            neg_etas = etas < 0 
            # Case A ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++           
            if rosi_in[1] < 0: # Has already violated, given the past. 
                # Case A1 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                if (t2-ts)+dt >= (d*dt): # Complete trace with the incrementally added points.  
                    # assert n_cmpln_stamps < 0 
                    eta = (rosi_in[1] * (d+1) + sum(etas[0:n_completed]*neg_etas[0:n_completed]))/(d+1)
                    return [eta,eta]
                #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # Case A2 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                else: 
                    assert n_cmpln_stamps > 0 
                    ueta = (rosi_in[1]*(d+1) + sum(etas*neg_etas))/(d+1)
                    leta = (rosi_in[0]*(d+1) - ((int((t2-t1)/dt)+1)*eta_min) + sum(etas*neg_etas))/(d+1)
                    assert int((t2-t1)/dt) > 0 
                    assert ueta >= leta, "leta must be <= ueta" 
                    return [leta,ueta]
                #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 
            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # Case B ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            else: # The past didn't violate: 
                # Case B1 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                if (t2-ts)+dt >= (d*dt): # The added points to the trace have completed the trajecotry
                    # return the actual robustness. 
                    assert n_cmpln_stamps <= 0 
                    eta = (((rosi_in[1]+1)**(d+1)*np.prod(1+(etas[0:n_completed]*np.invert(neg_etas[0:n_completed]))))
                           /(1+eta_max)**(int((d-t1)/dt)))**(1/(d+1)) - 1 
                    
                    # assert int((d-t1)/dt) > 0  # TODO [rt_dbgng]
                    return [eta,eta]
                #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # Case B2 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                else: 
                    # Case B21 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                    if np.any(neg_etas): # TODO [need_debugging]
                        # compute leta, ueta based on case 2 of eq(9)
                        ueta = (rosi_in[1]*(d+1)+sum(etas*neg_etas))/(d+1)
                        leta = (rosi_in[0]*(d+1)-(int((t2-t1)/dt))*eta_min+sum(etas*neg_etas))/(d+1)
                        assert int((t2-t1)/dt) > 0 
                        assert ueta >= leta
                        return [leta,ueta]
                    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                    # Case B22 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                    else: 
                        # compute leta, ueta based on case 1 of eq(9)
                        ueta = ((((rosi_in[1]+1)**(1+d)*np.prod(1+etas[0:-1]*np.invert(neg_etas[0:-1])))
                           /((1+eta_max)**(1+int((t2-t1)/dt))))**(1/(d+1))) - 1
                        # ueta = ((((rosi_in[1]+1)**(d)*np.prod(1+etas*np.invert(neg_etas)))
                        #    /((1+eta_max)**(1+int((t2-t1)/dt))))**(1/(d))) - 1
                        leta = ((int((d-t2)/dt))/(d+1))*eta_min
                        assert int((d-t2)/dt) > 0 
                        assert ueta >= leta
                        return [leta,ueta] 
                    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPARTIAL SINGNAL OBSERVATON <<
    elif formula.op == Op.WITHIN:
        #SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSINGELTON OBSERVATION >>
        # rosi_prev = 1 # Need to be fed or extracted from the vector of robustness intervals. 
        # assert rosi_in[0]==rosi_in[1]    # Not an atomoic proposition 
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        tp = t2
        a = formula.low
        b = formula.high
        N = int((b - a)/dt) # This N is just used in
        if rosi_prev==[]: # TODO []
            # The instantiation case. 
            if tp-ts > b: # Typically we start with a single observation of the system. 
                times = [t for t in times if ts+formula.low <= t <= t2] # Recall that t2 < t1+formula.high
                etas = np.array([agm_robustness(formula = formula.child, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                  for tau in times if np.any(np.logical_and(times>=tau,times<=t1+formula.high))],dtype=np.float64)
                eta = disjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)
                formula.rosi_eta = [eta,eta]
                assert leta <= ueta , "the lower bound is greater than the upper bound!"
                return [eta,eta]
            else: 
                times = [t for t in times if t1+formula.low <= t <= t2]
                n_cmpln_stamps = int((formula.high - (times[-1]-times[0]))/dt)
                etas_min , etas_max = np.repeat(-1,n_cmpln_stamps), np.repeat(1,n_cmpln_stamps)
                rosis = np.array([monitor_agm(formula = formula.child, trace=trace,times =  
                                                        times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                        for tau in times],dtype=np.float64)
                etas_l, etas_u = np.concatenate((rosis[:,0],etas_min)),np.concatenate((rosis[:,1],etas_max))
                ueta = disjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
                leta = disjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
                formula.rosi_eta = [leta,ueta]
                assert leta <= ueta , "the lower bound is greater than the upper bound!"
                return [leta,ueta]
        # Line 3-4:  
        if  rosi_prev[0]==rosi_prev[1] or rosi_prev[1]<0:
            if rosi_prev[1]<0:
                assert rosi_prev[1]==rosi_prev[0] , "For the within operator, when the upper bound is -ve, the computation of the lower bound should be the same. "
            formula.rosi_eta = rosi_prev
            return rosi_prev 
        # Line 5 - 10: 
        if tp - ts >= b: # Complete trajs; will return a singelton 
            if rosi_prev[1]<0:
                eta = -((1-rosi_in[1])*(1-rosi_prev[1]**(N))**(1./N))+1
            else: 
                eta = (N*rosi_prev[1]-eta_max+rosi_in[1])/(N)
            formula.rosi_eta = [eta,eta]
            assert leta <= ueta , "the lower bound is greater than the upper bound!"
            return [eta,eta]
        # Line 11 - 18:  
        else: 
            if rosi_prev[1]<0: 
                leta = -((1-rosi_in[1])*(1-rosi_prev[1]**(N))**(1./N))+1
                ueta = rosi_prev[1] - (eta_max/N)
            else: 
                # leta = -((((1-rosi_prev[0])**(N))*(1-rosi_in[0]))**(1./N))+1
                leta = -((((1-rosi_prev[0])**(N))/(1-eta_min))**(1./N))+1
                ueta = rosi_prev[1] - ((eta_max-rosi_in[0])/N)
            formula.rosi_eta = [leta,ueta]
            assert leta <= ueta , "the lower bound is greater than the upper bound!"
            return [leta,ueta]
        #SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSINGELTON OBSERVATION <<
        #PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPARTIAL SINGNAL OBSERVATON >>
        #PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPARTIAL SINGNAL OBSERVATON <<


        if len(times)==0 or t2 - t1 < formula.high: # For soundness, intuitively, we need long enough traces of the system  
            times = [t for t in times if t1+formula.low <= t <= t2]
            rosis = np.array([monitor_agm(formula = formula.child, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                  for tau in times],dtype=np.float64)
            etas_l, etas_u = rosis[:,0], rosis[:,1]
            ueta = disjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
            leta = disjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
            return [leta,ueta]
            # Do AGM upon the returned rosis: 
        else:
            times = [t for t in times if t1+formula.low <= t <= t2] # Recall that t2 < t1+formula.high
            etas = np.array([agm_robustness(formula = formula.child, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                  for tau in times if np.any(np.logical_and(times>=tau,times<=t1+formula.high))],dtype=np.float64)
            # times_ = [times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))] 
            #                     for tau in times[0:-1] if not np.any(np.logical_and(times>=tau,times<=t1+formula.high))>0]
            a = 1
            leta = disjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)
            return [leta,leta]
        
    elif formula.op in (Op.AND, Op.OR):
        rosis = np.array([monitor_agm(formula=child, trace=trace, times=times,dt = dt)
                        for child in [formula.left, formula.right]],dtype=np.float64)
        etas_l, etas_u = rosis[:,0], rosis[:,1]
        if formula.op == Op.OR: 
            ueta = disjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
            leta = disjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
        else: 
            ueta = conjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
            leta = conjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
        return [leta,ueta]
    elif formula.op == Op.CONCAT: 
        eta_min = -1
        eta_max = 1 
        times = list(times)
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        # dt = times[1] - times[0]
        true_time1 = np.array(times) >= formula.left.bounds_vls[0]
        true_time2 = np.array(times) < t2-formula.right.bounds_vls[0]
        if not np.any(np.logical_and(true_time1,true_time2)):
            rosis_1 = np.array([monitor_agm(formula = formula.left, trace=trace,
                                          times = times[np.where(np.logical_and(times>=t1,times<=tau))]
                                          ,dt=dt) for tau in times])
            # The completion for the 2nd subformula
            etas_min , etas_max = np.repeat(eta_min,len(rosis_1[:,0])), np.repeat(eta_max,len(rosis_1[:,0]))
            rosis_conl = np.array([conjunction_function(r_children = np.array([rosis_1[i,0],etas_min[i]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(rosis_1.shape[0])])
            rosis_conu = np.array([conjunction_function(r_children = np.array([rosis_1[i,1],etas_max[i]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(rosis_1.shape[0])])
            rosi = [disjunction_function(r_children = rosis_conl,pos_order = pos_order, neg_order = neg_order, plus=plus),\
                    disjunction_function(r_children = rosis_conu,pos_order = pos_order, neg_order = neg_order, plus=plus)]
            return rosi
        else:    
            rosis_t = np.array([(monitor_agm(formula = formula.left, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=t1,times<=tau))],dt=dt),
                            monitor_agm(formula = formula.right, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=tau+dt,times<=t2))],dt=dt)) \
                                                        for tau in times if 
                                                        tau >= formula.left.bounds_vls[0] and tau < t2-formula.right.bounds_vls[0]],dtype=np.float64)
            
            rosis_conl = np.array([conjunction_function(r_children = np.array([rosis_t[i,0,0],rosis_t[i,1,0]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(rosis_t.shape[0])])
            rosis_conu = np.array([conjunction_function(r_children = np.array([rosis_t[i,0,1],rosis_t[i,1,1]]),\
                        pos_order = pos_order, neg_order = neg_order, plus=plus) for i in range(rosis_t.shape[0])])
            rosi = [disjunction_function(r_children = rosis_conl,pos_order = pos_order, neg_order = neg_order, plus=plus),\
                    disjunction_function(r_children = rosis_conu,pos_order = pos_order, neg_order = neg_order, plus=plus)]
            return rosi
    else: 
        raise('the provided operator is not implementable')
def predicate_normalized_value(value=0, threshold=0, relation=None, rng=1.):
    '''Computes the normalized robustness value for a single predicate.

    Parameters
    ----------
    value     : float  — signal value at the evaluation time
    threshold : float  — predicate threshold
    relation  : int    — RelOperation code
    rng       : float  — normalization range (hi - lo of the signal variable)

    Returns
    -------
    float : signed distance, normalized by rng
    '''
    if relation in (RelOperation.GT, RelOperation.GE):
        eta = value - threshold
    elif relation in (RelOperation.LT, RelOperation.LE):
        eta = threshold - value
    elif relation == RelOperation.EQ:
        eta = -abs(value - threshold)
    elif relation == RelOperation.NQ:
        eta = abs(value - threshold)
    else:
        raise ValueError('Unknown relation code: {}'.format(relation))
    return eta / rng

# Backward-compatible alias
pred_nrmlizd_val = predicate_normalized_value
    

# @@@@@@ Incremental Runtime Monitor based on singeltons (Algorithm 1 in the paper): @@@@@@
'''Thing to look at: 
    - Instentiate a vector of robustness of the subformula 
'''
def incremental_monitor_agm(formula, 
                   ast_rosi = None , 
                   times = None,
                   trace = None, 
                   t1=None,t2=None,tp_end=0, ts = 0, 
                   pos_order=0, neg_order=1,
                   maximum_robustness=1, 
                   plus=0,dt = 1, 
                   rosi_prime = None,
                   rosi_vec = None, # XXX rosi_vec need to be as the aggragated rosis of the AST; I have added this to the AST class as an attribute to every node in the tree.  
                   rosi_prev = [], 
                   rt_mntrg_flg = True, 
                   word_mntrg_flg = False, 
                   obs_mntrg_flg = True ):           
    '''
    Input/parameters: 
    formula: The abstract syntax tree of the formula, 
    times: The time trajectory of the given partial signal 
    trace: The trace of the system, (will be truncated based on times)
    t1:        The initial time stamp of the times, 
    t2:        The final time stamp of times
    ts:        The initial time of the history. 

    Outputs: 
    [ueta, leta]: AGM robustness interval, an interval semantics for the true AGM robustness given partial run of the system

    '''
    # NOTE: distinguish between rosi_p and rosi_in. In Cristi's algorithm rosi_p is the aux rosi; in this code it's the previous rosi
    assert trace is not None
    
    # if rosi_p is not None: TODO [ask cristi] 
    #     return rosi_p
    eta_min, eta_max = -1.,1.
    if formula.op == Op.NOP: #Predicated proposition 
        raise('the provided operator is not implementable')
    elif formula.op == Op.PRED:
        value = trace.value(formula.variable, times)
        rng = trace.range(formula.variable) 
        ueta = predicate_normalized_value(value=value,threshold=formula.threshold,relation=formula.relation,rng=rng)
        formula.rosi_eta = [leta,ueta]
        return [ueta,ueta]
    elif formula.op == Op.HOLD:
        # Precomputation settings: 
        # rosi_prev = rosi_vec # TODO [code inc]
        # >>> Assigning the max and min etas as -+1. For the Lipschitz monitoring, though,  we need to compute them online 
        # eta_min, eta_max = -1.,1.
        # <<<
        # Line 14 of Algorithm (computing the aux rosi, rosi_p):
        # ---------------------------------------        
        if obs_mntrg_flg:
            value = trace.value(formula.variable, times)
            rng = trace.range(formula.variable) 
            ueta = predicate_normalized_value(value=value,threshold=formula.threshold,relation=formula.relation,rng=rng)
            rosi_prime = [ueta,ueta]
        elif word_mntrg_flg: 
            pass # TODO [code cont]
        # ---------------------------------------
        d = formula.duration
        if len(times)==0:
            raise
            formula.rosi_eta = [-1,1]
            return [-1,1] 
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        times = [t for t in times if t1 <= t <= (d*dt)+t1]
        tp = t2
        # rosi_in = rosi_prime 
        # rosi_in = [] # The previous rosi
        assert rosi_prime[0]==rosi_prime[1] # Given it's computed at a single time-less point
        if rosi_prime[0]<0: 
            eta_prime_neg = -rosi_prime[0]
            eta_prime_pos = 0.
        else: 
            eta_prime_neg = 0.
            eta_prime_pos = rosi_prime[0]
        
        ##SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSINGELTON OBSERVATION >>
        if obs_mntrg_flg: # Algorithm 2 in the paper, (IRTM_H) 
            if rosi_prev == []: # Oct-11 In the case of the within operator I need to have a rosi_prev for each cut-signal 
                rosi = monitor_agm(formula, times ,trace = trace, t1=None,t2=None, pos_order=0, neg_order=1,
                         maximum_robustness=1, plus=0,dt = dt)  # Computing using (Eq 16) Monitor in the case of the intial monitoring iteration
                # TODO [testing Robrto]: 
                
                # rosi_u = updt_gmtrc_rosi(n_rplc = 1, rosi_bnd_rplc = rosi_prime[1],rosi_bnd = 1., pos_flg = True, eta_max = 1., eta_min = -1.,dt = dt,d = d)
                # a = 1

                # TODO the set of completions should depend on the deadline based on the outer formula 
                # TODO [sanity check] 
                # TODO [code cont] Currently we use monitor_agm(.) as the function which computes given partial signal
                # TODO [code cont] code the partial signal part in inc_mntrng_agm  
                # times_d = copy.deepcopy(times)
                # rosi = inc_monitor_agm(formula, times = times ,trace = trace, t1=None,t2=None, pos_order=0, neg_order=1,
                #          maximum_robustness=1, plus=0,dt = 0.1)
                formula.rosi_eta = rosi
                return rosi
            # The correct computation of H rosi: 
            # if tp - ts >= d:
            #     assert rosi_prev[1] > 0 , 'There is still hope since the signal is less than the time horizon' 
            #     # If the nve counter > 0, compute ueta 
            # if rosi_prev[1] < 0: 
                

            #     if tp - ts >= d:
            #         eta = (rosi_prev[1]*(d+dt)+eta_prime_neg)*(1./(d+dt))
            #         formula.rosi_eta = [eta,eta]
            #         return [eta,eta] 
            #     else:
            #         leta = (rosi_prev[0]*(d+dt)-eta_min+eta_prime_neg)*(1./(d+dt))
            #         ueta = (rosi_prev[1]*(d+dt)+eta_prime_neg)*(1./(d+dt))
            #         formula.rosi_eta = [leta,ueta]
            #         return [leta,ueta]
            # else: 
            #     if tp_end - ts >= d:
            #         eta = ((1+eta_prime_pos)*(rosi_prev[1]+1)^(d+dt)/(1+eta_max))**(1/(d+dt))-1
            #         formula.rosi_eta = [leta,ueta]
            #         return [eta,eta]
            #     else:
            #         if rosi_prime[0] < 0: 
            #             leta = ((rosi_prev[0]*(d+dt))+eta_prime_neg)*(1/(d+dt))
            #             ueta = ((rosi_prev[0]*(d+dt))-eta_min+eta_prime_neg)*(1/(d+dt))
            #         else: 
            #             leta = eta_min/(d+dt)
            #             ueta = ((((eta_prime_pos+1)*(rosi_prev[1]+1)**(d+dt))/(1+eta_max))**(1/(d+dt)))-1
            #         formula.rosi_eta = [leta,ueta]
            #         return [leta,ueta]            

            
            # XXX ---

            # TODO Count the number of consequitive changes in the sign and based on that we decide which part to unravle
            if rosi_prev[1] < 0: 
                if tp - ts >= d:
                    eta = (rosi_prev[1]*(d)+eta_prime_neg)*(1./(d))            # Done, FIXME, check d+dt, make sure powermean() is done correctly here.
                    formula.rosi_eta = [eta,eta]
                    return [eta,eta] 
                else:
                    leta = (rosi_prev[0]*(d)-eta_min+eta_prime_neg)*(1./(d))    #  Done, FIXME, check d+dt
                    ueta = (rosi_prev[1]*(d)+eta_prime_neg)*(1./(d))            #  Done, FIXME, check d+dt
                    formula.rosi_eta = [leta,ueta]
                    return [leta,ueta]
            else: 
                if tp - ts >= d:
                    # eta = ((1+eta_prime_pos)*((rosi_prev[1]+1)**(d+dt))/(1+eta_max))**(1/(d+dt))-1
                    eta_d = -1+(rosi_prev[1]+1)*((1+eta_prime_pos)/(1+eta_max))**(1/(d+1))
                    eta = update_geometric_rosi(n_rplc = 1, rosi_bnd_rplc = rosi_prime[1],rosi_bnd = rosi_prev[1], pos_flg = True, eta_max = 1., eta_min = -1.,dt = dt,d = d)
                    assert eta <= 1 and eta >= 0
                    formula.rosi_eta = [eta,eta]
                    return [eta,eta]
                    
                else:
                    if rosi_prime[0] < 0: 
                        leta = ((rosi_prev[0]*(d))+eta_prime_neg)*(1/(d))
                        ueta = ((rosi_prev[0]*(d))-eta_min+eta_prime_neg)*(1/(d))
                    else: 
                        leta = eta_min/(d)
                        ueta_d = -1+ (rosi_prev[1]+1) * ((((eta_prime_pos+1))/(1+eta_max))**(1/(d)))
                        ueta = update_geometric_rosi(n_rplc = 1, rosi_bnd_rplc = rosi_prime[1],rosi_bnd = rosi_prev[1], pos_flg = True, eta_max = 1., eta_min = -1.,dt = dt,d = d)
                        assert ueta > 0
                    formula.rosi_eta = [leta,ueta]
                    return [leta,ueta]
        ##SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSINGELTON OBSERVATION <<
        #PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPARTIAL SINGNAL OBSERVATON >>
        if word_mntrg_flg: 
            if rosi_prev is None:  
                rosi = monitor_agm(formula, times ,trace = None, t1=None,t2=None, pos_order=0, neg_order=1,
                        maximum_robustness=1, plus=0,dt = 0.1)  # Monitor in the case of the intial monitoring iteration
                formula.rosi_eta = rosi
                return rosi
            # Case 0: ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            if rosi_prev[0]==rosi_prev[1]: # The case if I already have complete signals that satisfied the specs:
                formula.rosi_eta = rosi_prev
                return rosi_prev
            #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            #compute rosi given the new subtraj:  
            n_cmpln_stamps = int(((d*dt) - (times[-1]-ts))/dt) # Number of completions given the original signal 
            n_completed    =  int(((d*dt) - (times[0]-ts+dt))/dt) # Number of points needed for completed signal given the new signal
            n_stamps = int((d)/dt)+1                      # Given the bound of TWTL formula
            if n_cmpln_stamps < 0:
                raise TypeError('not implemented')               
            if n_cmpln_stamps>0:
                # Will be just used in case: A2, B2 (or maybe not needed at all)
                etas_min , etas_max = np.repeat(eta_min,n_cmpln_stamps), np.repeat(eta_max,n_cmpln_stamps) 

            # The computation of eta for a predicate 
            if formula.nf_subformula is not None:
                nf_subformula = formula.nf_subformula
                if not (nf_subformula.op in (Op.AND, Op.OR)): 
                    raise('No NF subformula is given.')
                etas = np.array([agm_robustness(formula = nf_subformula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # after these being computed, search if any violates the specs and compute the A or G robustness
                # TODO [rt_dbgng] Make sure to include the needed points when computing the robustness intervals; 
            else: 
                predFormula = copy.copy(formula)
                predFormula.op = Op.PRED
                etas = np.array([agm_robustness(formula = predFormula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64)
            neg_etas = etas < 0 
            # Case A ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++           
            if rosi_prev[1] < 0: # Has already violated, given the past. 
                # Case A1 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                if (t2-ts)+dt >= (d*dt): # Complete trace with the incrementally added points.  
                    # assert n_cmpln_stamps < 0 
                   eta = (rosi_prev[1] * (d+1) + sum(etas[0:n_completed]*neg_etas[0:n_completed]))/(d+1)
                   formula.rosi_eta = [eta,eta]
                   return [eta,eta]
                #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # Case A2 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                else: 
                    assert n_cmpln_stamps > 0 
                    ueta = (rosi_prev[1]*(d+1) + sum(etas*neg_etas))/(d+1)
                    leta = (rosi_prev[0]*(d+1) - ((int((t2-t1)/dt)+1)*eta_min) + sum(etas*neg_etas))/(d+1)
                    assert int((t2-t1)/dt) > 0 
                    assert ueta >= leta, "leta must be <= ueta" 
                    formula.rosi_eta = [leta,ueta]
                    return [leta,ueta]
                #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++ 
            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            # Case B ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            else: # The past didn't violate: 
                # Case B1 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                if (t2-ts)+dt >= (d*dt): # The added points to the trace have completed the trajecotry
                    # return the actual robustness. 
                    assert n_cmpln_stamps <= 0 
                    eta = (((rosi_prev[1]+1)**(d+1)*np.prod(1+(etas[0:n_completed]*np.invert(neg_etas[0:n_completed]))))
                           /(1+eta_max)**(int((d-t1)/dt)))**(1/(d+1)) - 1 
                    
                    # assert int((d-t1)/dt) > 0  # TODO [rt_dbgng]
                    formula.rosi_eta = [eta,eta]
                    return [eta,eta]
                #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                # Case B2 +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                else: 
                    # Case B21 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                    if np.any(neg_etas): # TODO [need_debugging]
                        # compute leta, ueta based on case 2 of eq(9)
                        ueta = (rosi_prev[1]*(d+1)+sum(etas*neg_etas))/(d+1)
                        leta = (rosi_prev[0]*(d+1)-(int((t2-t1)/dt))*eta_min+sum(etas*neg_etas))/(d+1)
                        assert int((t2-t1)/dt) > 0 
                        assert ueta >= leta
                        formula.rosi_eta = [leta,ueta]
                        return [leta,ueta]
                    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                    # Case B22 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
                    else: 
                        # compute leta, ueta based on case 1 of eq(9)
                        ueta = ((((rosi_prev[1]+1)**(1+d)*np.prod(1+etas[0:-1]*np.invert(neg_etas[0:-1])))
                           /((1+eta_max)**(1+int((t2-t1)/dt))))**(1/(d+1))) - 1
                        # ueta = ((((rosi_prev[1]+1)**(d)*np.prod(1+etas*np.invert(neg_etas)))
                        #    /((1+eta_max)**(1+int((t2-t1)/dt))))**(1/(d))) - 1
                        leta = ((int((d-t2)/dt))/(d+1))*eta_min
                        assert int((d-t2)/dt) > 0 
                        assert ueta >= leta
                        formula.rosi_eta = [leta,ueta]
                        return [leta,ueta] 
                    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        else: 
            raise("No monitring type chosen.")
    #PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPARTIAL SINGNAL OBSERVATON <<
    elif formula.op == Op.WITHIN:
        
        #SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSINGELTON OBSERVATION >>
        if obs_mntrg_flg: 
            # rosi_prev = 1 # Need to be fed or extracted from the vector of robustness intervals. 
            # assert rosi_in[0]==rosi_in[1]    # Not an atomoic proposition 
            if t1 is None and t2 is None:
                t1,t2 = times[0],times[-1]
            tp = t2
            a = formula.low
            b = formula.high
            N = int((b - a)/dt) # This N is just used in
            if tp < a:         # Oct-11 step 0 in the picture.
                return [-1,1] # Oct-11 step 0 in the picture. 
            if rosi_prev==[]: # Line 4-6 in Algorithm 3. Compute rosi using eq(16)
                # The instantiation case. 
                raise Exception('how! Well it could happen if my formula is []^[0,b]')
                if tp-ts > b: # Typically we start with a single observation of the system. 
                    times = [t for t in times if ts+formula.low <= t <= t2] # Recall that t2 < t1+formula.high
                    etas = np.array([agm_robustness(formula = formula.child, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                    for tau in times if np.any(np.logical_and(times>=tau,times<=t1+formula.high))],dtype=np.float64)
                    eta = disjunction_function(r_children = etas, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    formula.rosi_eta = [eta,eta]
                    assert leta <= ueta , "the lower bound is greater than the upper bound!"
                    formula.rosi_eta = [leta,ueta]
                    return [eta,eta]
                else: 
                    # times = [t for t in times if t1+formula.low <= t <= t2]
                    times = [t for t in times if ts+formula.low <= t <= t2]
                    n_cmpln_stamps = int((formula.high - (times[-1]-times[0]))/dt)
                    etas_min , etas_max = np.repeat(-1,n_cmpln_stamps), np.repeat(1,n_cmpln_stamps)
                    rosis = np.array([inc_monitor_agm( formula = formula.child, 
                                                    times = times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],
                                                    trace = trace, 
                                                    ts = ts, 
                                                    pos_order=0, neg_order=1,
                                                    maximum_robustness=1, 
                                                    plus=0,dt = dt,    
                                                    rosi_prev = formula.child.rosi_eta) for tau in times],dtype=np.float64)
                    # TODO [code inc]
                    # rosis = np.array([monitor_agm(formula = formula.child, trace=trace,times =  
                    #                                         times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                    #                                         for tau in times],dtype=np.float64)
                    etas_l, etas_u = np.concatenate((rosis[:,0],etas_min)),np.concatenate((rosis[:,1],etas_max))
                    ueta = disjunction_function(r_children = etas_u, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    leta = disjunction_function(r_children = etas_l, pos_order = pos_order, neg_order = neg_order, plus=plus)
                    formula.rosi_eta = [leta,ueta]
                    assert leta <= ueta , "the lower bound is greater than the upper bound!"
                    formula.rosi_eta = [leta,ueta]
                    if etas_u[0]>0:
                        formula.urosi_prime_pve_cntr = formula.urosi_prime_pve_cntr +1
                    if etas_l[0]>0: 
                        formula.lrosi_prime_pve_cntr = formula.lrosi_prime_pve_cntr +1
                    return [leta,ueta]
            # Line 7-8:  
            if  rosi_prev[0]==rosi_prev[1]:# or rosi_prev[1]<0:
                # if rosi_prev[1]<0:
                #     formula.rosi_eta = rosi_prev
                #     return [rosi_prev[1],rosi_prev[1]] 
                # TODO [sci]
                # if rosi_prev[1]<0:
                #     assert rosi_prev[1]==rosi_prev[0] , "For the within operator, when the upper bound is -ve, the computation of the lower bound should be the same. "
                formula.rosi_eta = rosi_prev
                return rosi_prev 
            # Line 9 - 14: 
            # Oct-11 \/\/\/\/ 

            # Step 2 Compute rosi_prime/s: TODO create an attribute for the grwoing rosis and make sure to reinstantiate after you finish. 
            # Assuming that the formula is [phi]^[a,b]
            
            # if formula.rosis4W ==[]: 
            #     rosi_prime_prev_init = []
            # else: 
            #     rosi_prime_prev_init = formula.rosis4W[0]
            rosi_phi_prime = inc_monitor_agm(formula= formula.child,
                                        times=times,
                                        trace=trace,
                                        pos_order=pos_order,
                                        neg_order=neg_order,
                                        rosi_prev=[],dt=dt)             
            for iphi_prime,rosi_phi_prime_p1ANDtsp1 in enumerate(formula.rosis4W): 
                formula.rosis4W[iphi_prime][0] = inc_monitor_agm(formula= formula.child,
                                                                times=times,
                                                                trace=trace,
                                                                ts = rosi_phi_prime_p1ANDtsp1[1], 
                                                                pos_order=pos_order,
                                                                neg_order=neg_order,
                                                                rosi_prev=rosi_phi_prime_p1ANDtsp1[0],dt=dt)        
            formula.rosis4W.append([rosi_phi_prime,times[0]])
            times_shifted = 1
            # making sure that the trace is with the correct time stamp 
      
            
            
            
            # Step 4 Update the rosi_prime/s prevs: 
            # Step 3 continue the computation of the rosi!
            # Oct-11 ^^^^

            
            # -- -- needed precomputations: 
            # With the assupmtion that \psi is a hold operator: 
            
            # Commented OUT FOR DEBUGGING
            # rosi_prime = inc_monitor_agm(formula= formula.child,
            #                             times=times,
            #                             trace=trace,
            #                             pos_order=pos_order,
            #                             neg_order=neg_order,
            #                             rosi_prev=formula.child.rosi_eta,dt=dt) # Oct-11 
            # if rosi_prime[1]>0:
            #     formula.urosi_prime_pve_cntr = formula.urosi_prime_pve_cntr +1
            # if rosi_prime[0]>0: 
            #     formula.lrosi_prime_pve_cntr = formula.lrosi_prime_pve_cntr +1
            # rosi_prime_neg = (np.array(rosi_prime) < 0 ) * rosi_prime 
            # rosi_prime_pos = (np.array(rosi_prime) > 0 ) * rosi_prime
            
            # if tp - ts >= b: # Complete trajs; will return a singelton 
            #     if rosi_prev[1]<0:
            #         raise 'This case should not happen unless we have complete signal! Since we still have one observation that actually may yield satisfaction.'
            #     if formula.urosi_prime_pve_cntr > 0: 
            #         eta = rosi_prev[1] + ((rosi_prime_pos[1]-eta_max)/N)
            #     else: 
            #         if rosi_prime[1]>0:
            #             eta = (rosi_prime_pos[1]/N)
            #         else: 
            #             eta = -(((1-rosi_prime[1])*((1-rosi_prev[1])**(N))/(1-eta_min))**(1./N))+1
            #     formula.rosi_eta = [eta,eta]
            #     # assert leta <= ueta , "the lower bound is greater than the upper bound!"
            #     formula.rosi_eta = [eta,eta]
            #     return [eta,eta]
            # # Line 15 - 22:  
            # else: 
            #     if rosi_prev[1]<0: # Line 
            #         raise 'This case should not happen unless we have complete signal! Since we still have possible observations that actually may yield satisfaction.'
            #     if formula.urosi_prime_pve_cntr > 0:
            #         # For both leta and ueta, unravle arithmatic mean 
            #         leta = rosi_prev[0] + ((rosi_prime_pos[0]-eta_max)/N) # rosi_prime_pos[0] must be 0 
            #         assert rosi_prime_pos[0] == 0
            #         assert leta >  0
            #         ueta = rosi_prev[1] + ((rosi_prime_pos[1]-eta_max)/N)
            #         assert ueta >= leta
            #     else: 
            #         # leta --------
            #         # For leta, assert leta < 0, if leta_prime>0 compute leta using the Amean 
            #         # if leta_prime<0 unravel the geomtric mean and compute leta using the geometric mean 
            #         assert rosi_prev [0] < 0 
            #         if rosi_prime[0] > 0: 
            #             leta = rosi_prime_pos[0] / N
            #             assert rosi_prime_pos[0] > 0 
            #         else: 
            #             leta = -(((1-rosi_prime[0])*((1-rosi_prev[0])**(N))/(1-eta_min))**(1./N))+1
            #         # ueta --------
            #         # Unravel the Amean and accomdate the computation. 
            #         # If ueta_prime < 0 ueta will get decresed more than if ueta_prime > 0  
            #         ueta = rosi_prev[1] + ((rosi_prime_pos[1]-eta_max)/N)


            #     assert leta <= ueta , "the lower bound is greater than the upper bound!"
            #     assert ueta <=1.
            #     formula.rosi_eta = [leta,ueta]
            #     return [leta,ueta]
            return [-1,1] # Commented OUT FOR DEBUGGING
            # Commented OUT FOR DEBUGGING
            
            
            # XXX THE (WRONG) ALGORITHM 3 IN THE MANUSCRIPT: 
            if tp - ts >= b: # Complete trajs; will return a singelton 
                if rosi_prev[1]<0:
                    raise 'This case should not happen unless we have complete signal! Since we still have one observation that actually may yield satisfaction.'
                    eta = -(((1-rosi_prime[0])*(1-rosi_prev[1]**(N))/(1-eta_min))**(1./N))+1
                else: 
                    eta = (N*rosi_prev[1]-eta_max+rosi_prime_pos[1])/(N)
                formula.rosi_eta = [eta,eta]
                # assert leta <= ueta , "the lower bound is greater than the upper bound!"
                formula.rosi_eta = [eta,eta]
                return [eta,eta]
            # Line 15 - 22:  
            else: 
                if rosi_prev[1]<0: # Line 
                    raise 'This case should not happen unless we have complete signal! Since we still have possible observations that actually may yield satisfaction.'
                    leta = -(((1-rosi_prime_neg[0])*((1-rosi_prev[1])**(N))/(1-eta_min))**(1./N))+1
                    ueta = rosi_prev[1] + ((rosi_prime_pos[1]-eta_max)/N)
                else: 
                    # leta = -((((1-rosi_prev[0])**(N))*(1-rosi_in[0]))**(1./N))+1
                    leta = -((((1-rosi_prev[0])**(N))/(1-eta_min))**(1./N))+1
                    ueta = rosi_prev[1] - ((eta_max-rosi_prime[1])/N)
                assert leta <= ueta , "the lower bound is greater than the upper bound!"
                assert ueta <=1.
                formula.rosi_eta = [leta,ueta]
                return [leta,ueta]
            #SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSINGELTON OBSERVATION <<
        elif word_mntrg_flg:
            pass
            #PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPARTIAL SINGNAL OBSERVATON >>
            #PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPARTIAL SINGNAL OBSERVATON <<
        else: 
            raise('No specific monitoring type is provided!')
        
    elif formula.op == Op.CONCAT: 
        # TODO [code inc] I need to increment the time proprly 
        
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        tp = t2
        if obs_mntrg_flg: 
            # Compute the number of time steps that we monitored (observed) so far:
            n_obs = int((tp-(ts-dt)/dt)) 
            assert n_obs > 0 , "neumerical error in the computation of the number of the observed data"
            if n_obs == 1: # The first observation point  
                # # Need to be computed and then update the rosi_phi1; which will be increased in time 
                # (will actually since the memory is bounded be the horizon; we may as well instentiated as well)
                rosi_phi1_req = inc_monitor_agm(formula=formula.left,
                                               times=times,
                                               trace=trace,
                                               ts=ts,dt=dt,
                                               rosi_prev=[])    
                # Update the memory of rosis:
                formula.rosis_left.append(rosi_phi1_req)
                formula.rosi_eta = [-1.,1.]
                return [-1.,1.]
            
            elif n_obs == 2: # The 2nd case when I need to devide exactly  
                
                # Devide the time trajectory into two:
                # t1_traj = np.array([times[0]])
                t2_traj = np.array([times[0]]) # TODO [code inc] Do I really need a 0 time step? 
                
                # Compute rosi for singltons 
                # rosi_phi1 = inc_monitor_agm(formula=formula.right,times=t1_traj,trace=trace,ts=ts,dt=dt,rosi_p=None)
                rosi_phi1 = formula.rosis_right[0]
                rosi_phi2 = inc_monitor_agm(formula = formula.left, 
                                  times = t2_traj,
                                  trace = trace,
                                  pos_order = pos_order, 
                                  neg_order = neg_order,
                                  dt = dt,
                                  rosi_prev = formula.rosis_left[-1], 
                                  rt_mntrg_flg = False,
                                  ts = tp) #TODO [code inc] what should ts be? 
                # inc_monitor_agm(formula=formula.left,times=t2_traj,trace=trace,ts=ts,dt=dt,rosi_p=None)
                # Compute the conjunction of rosi_phi1 and rosi_phi2: 
                leta = conjunction_function(r_children = np.array([rosi_phi1[0],rosi_phi2[0]]),pos_order = pos_order, neg_order = neg_order, plus=plus)
                ueta = conjunction_function(r_children = np.array([rosi_phi1[1],rosi_phi2[1]]),pos_order = pos_order, neg_order = neg_order, plus=plus)
                formula.rosi_eta = [leta,ueta]
                return [leta,ueta]
            else:   # the recursive case :  
                # Extract the memory: 
                rosis_phi1 = formula.rosis_left      # Rosis to be pushed
                rosis_phi2 = copy.deepcopy(formula.rosis_right)     # Rosis that will be used to compute their robustneses incrementally
                # Compute the nonincremental (singelton):
                times2 = np.array([tp])
                rosi_tptp_phi2 =  inc_monitor_agm(formula = formula.right, 
                                  times = times2,
                                  trace = trace,
                                  pos_order = pos_order, 
                                  neg_order = neg_order,
                                  dt = dt, 
                                  rt_mntrg_flg = False,
                                  ts = tp) #TODO [code inc] what should ts be? NO XDXDXDXDX!!!!!!!!!!
                
                # Compute the incremental peices:
                #------------------------------------------------------------
                assert times-dt > 0 
                rosi_tp_1_phi1 = inc_monitor_agm(formula = formula.left, 
                                  times = times-dt,
                                  trace = trace,
                                  pos_order = pos_order, 
                                  neg_order = neg_order,
                                  dt = dt,
                                  rosi_prev=rosis_phi1[-1], 
                                  rt_mntrg_flg = False,
                                  ts = ts) #TODO [code inc] what should ts be?
                # Updating the rosis of phi2 incremently: 
                for i,rosi in enumerate(rosis_phi2): 
                    rosi = inc_monitor_agm(formula = formula.right, 
                                  times = times,
                                  trace = trace,
                                  pos_order = pos_order, 
                                  neg_order = neg_order,
                                  dt = dt, 
                                  rosi_prev=rosi,
                                  rt_mntrg_flg = False,
                                  ts = tp-(i+1)*dt) #TODO [code inc] what should ts be? NO XDXDXDXDX!!!!!!!!!!
                    
                    # inc_monitor_agm(formula=formula.left,times=times,trace=trace,ts=ts,dt=dt,rosi_p=rosi) 
                    formula.rosis_right[-i-1] = rosi 
                
                # Pushing the values of rosis: 
                formula.rosis_left.append(rosi_tp_1_phi1) # Just appending!
                formula.rosis_right.append(rosi_tptp_phi2) # Appending after having updated the all the elemnts of formula.rosis_right
                # Compute the conjunction cases:
                rosis_conl = np.array([conjunction_function(r_children = np.array([rosi1[0],rosi2[0]]),\
                            pos_order = pos_order, neg_order = neg_order, plus=plus) for rosi1, rosi2  in zip(formula.rosis_left,formula.rosis_right)])
                rosis_conu = np.array([conjunction_function(r_children = np.array([rosi1[1],rosi2[1]]),\
                            pos_order = pos_order, neg_order = neg_order, plus=plus) for rosi1, rosi2  in zip(formula.rosis_left,formula.rosis_right)])
                # Compute the disjunction case:
                rosi_r = [disjunction_function(r_children = rosis_conl,pos_order = pos_order, neg_order = neg_order, plus=plus),\
                        disjunction_function(r_children = rosis_conu,pos_order = pos_order, neg_order = neg_order, plus=plus)]
                formula.rosi_eta = rosi_r
                return rosi_r
        elif word_mntrg_flg: 
            pass
            if ts == t1: # The first encauterd word of observations:  
                pass
            else:        # the recursive case; need to be mathmatically formulated
                pass 
        else: 
            raise('No specific monitoring type is provided!')
    else: 
        raise('the provided operator is not implementable')
def update_geometric_rosi(n_comp=None, n_rplc=1, rosi_bnd_rplc=1,
                          rosi_bnd=1, pos_flg=True,
                          eta_max=1., eta_min=-1., dt=1, d=10):
    '''Updates the geometric-mean robustness bound by unraveling the equation.

    Parameters
    ----------
    n_rplc        : int   — number of replacement time steps
    rosi_bnd_rplc : float — robustness bound for the replacing observation
    rosi_bnd      : float — current robustness bound to update
    pos_flg       : bool  — True if the bound is positive (geometric unravel)
    eta_max / eta_min : float — signal normalization extremes
    dt, d         : float — time step and formula duration

    Returns
    -------
    float : updated robustness bound
    '''
    if pos_flg:
        return -1. + (rosi_bnd + 1.) * (((rosi_bnd_rplc + 1.) / (1. + eta_max))
                                         ** (1. / d))
    else:
        return 1. - (1. - rosi_bnd) * (((1. - rosi_bnd_rplc) / (1. - eta_min))
                                        ** (1. / d))

# Backward-compatible alias
updt_gmtrc_rosi = update_geometric_rosi


def update_arithmetic_rosi(n_comp, n_rplc=1, rosi_bnd=1, pos_flg=True):
    '''Updates the arithmetic-mean robustness bound. (Not yet implemented.)'''
    pass

# Backward-compatible alias
updt_arthc_rosi = update_arithmetic_rosi


# @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@



# Traditional robustness:
# ==============================================================================================

def robustness(formula,times,t1=None,t2=None,trace = None,dt = .1):#t1=0,t2=None,shift = 0):
    '''
    - Ahmad Ahmad 

    This method computes the quantitative semantics for a observations w.r.t. to TWTL formula
    @input formula: a TWTL formula defined over linear predicates 
    @input word: a sequence of word (typically observable trajectory generated by state trajectory of a transition system)
    @param t1: the initial time step to be considered from the word (integer number) 
    @param t1: the final time step to be considered from the word (integer number)

    @return: rho: the spatial robustness of the word w.r.t. TWTL formula 
    
    '''
    # assert t_1, t_2 are integers and 0=<t_1<=t_2<len(word)
    
    # TODO: Create a trace class 
    #------------------------------------------
    # n_traces = trace.number_signals()
    # traj = 111111
    assert trace is not None
    if formula.op == Op.NOP: #Predicated proposition 
        pass
    elif formula.op == Op.PRED:
        value = trace.value(formula.variable, times)
        if formula.relation in (RelOperation.GT, RelOperation.GE):
            rho = value - formula.threshold
        elif formula.relation in (RelOperation.LT, RelOperation.LE):
            rho = formula.threshold - value
        elif formula.relation == RelOperation.EQ:
            rho = -abs(value - formula.threshold)
        elif formula.relation == RelOperation.NQ:
            rho = abs(value - formula.threshold)
        return rho 
        
    elif formula.op == Op.HOLD:
        d = formula.duration
        
        if len(times)==0:
            return float('-Inf')
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        times = [t for t in times if t1 <= t <= (d*dt)+t1]
        if (t2 - t1)+dt < (d*dt):
            rho = float('-Inf')
        else: 
            # traj = trace.value(formula.variable,times[0:-1])
            if formula.nf_subformula is not None: # A conjunction of predicates: 
                nf_subformula = formula.nf_subformula
                if not (nf_subformula.op in (Op.AND, Op.OR)): 
                    raise('No NF subformula is given.')
                # Compute eta at each time instance: 
                 # At each time instance we'll compute the AGM for a conjunctive formula: 
                rhos = np.array([robustness(formula = nf_subformula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # after these being computed, search if any violates the specs and compute the A or G robustness
                rho = min(rhos) 
            else: # If the child is a singleton (a linear predicate).  
                predFormula = copy.copy(formula)
                predFormula.op = Op.PRED
                rhos = np.array([robustness(formula = predFormula, trace=trace,times = tau,dt = dt)
                                    for tau in times],dtype=np.float64) # FIXME the predicate should be a child of the holdFormula
                rho = min(rhos)
        return rho
    elif formula.op == Op.WITHIN:
        if len(times)==0:
            return float('-inf')
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        if t2 - t1 < formula.high:
            rho = float('-Inf')
        else:
            times = [t for t in times if t1+formula.low <= t <= t1+formula.high]
            rho = [robustness(formula = formula.child, trace= trace, times=np.array(times),t1 = t, t2 = times[0]+formula.high,dt = dt) for t in times] # These are predicated propositions 
            rho = max(rho)
        return rho
    elif formula.op in (Op.OR,Op.AND):
        # times = [t]
        rho = [robustness(formula= f,trace= trace,times=times,dt=dt) for f in [formula.left,formula.right]]
        if formula.op == Op.OR: 
            rho = max(rho)
        else: 
            rho = min(rho)
        return rho
    elif formula.op == Op.NOT: 
        rho = -robustness(formula= formula,trace=trace,times=times,dt=dt)
        return rho
    elif formula.op == Op.CONCAT:
        times = list(times)
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        rhos = np.array([(robustness(formula = formula.left, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=t1,times<=tau))],dt=dt),
                           robustness(formula = formula.right, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau+dt,times<=t2))],dt=dt)) 
                        for tau in times if tau >= formula.left.bounds_vls[0] and tau < t2-formula.right.bounds_vls[0]],dtype=np.float64)
        if len(rhos) == 0: 
            return float('-inf')
        rhoss_con = np.array([min((rhos[i,0],rhos[i,1]))for i in range(rhos.shape[0])])
        rho = max(rhoss_con)
        return rho
    else: 
        raise('You are not accounting for op:%d',formula.op)
    

def monitor_robustness(formula, times ,trace = None, t1=None,t2=None, pos_order=0, neg_order=1,
                         maximum_robustness=1, plus=0,dt = 0.1):
    '''
 
    Input/parameters: 
    formula: The abstract syntax tree of the formula, 
    times: The time trajectory of the given partial signal 
    trace: The trace of the system, (will be truncated based on times)
    t1:        The initial time stamp of the times, 
    t2:        The final time stamp of times

    Outputs: 
    [ueta, leta]: Regular robustness interval, an interval semantics for the true AGM robustness given partial run of the system

    '''
    assert trace is not None
    if formula.op == Op.NOP: #Predicated proposition 
        pass
    elif formula.op == Op.PRED:
        value = trace.value(formula.variable, times)
        if formula.relation in (RelOperation.GT, RelOperation.GE):
            rho = value - formula.threshold
        elif formula.relation in (RelOperation.LT, RelOperation.LE):
            rho = formula.threshold - value
        elif formula.relation == RelOperation.EQ:
            rho = -abs(value - formula.threshold)
        elif formula.relation == RelOperation.NQ:
            rho = abs(value - formula.threshold)
        return [rho,rho]
    
    elif formula.op == Op.HOLD:
        # >>> Assigning the max and min etas as -+1. For the Lipschitz monitoring, though,  we need to compute them online 
        rho_min, rho_max = float('-inf'),float('inf')
        # <<<
        d = formula.duration
        if len(times)==0:
            return -1 
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        times = [t for t in times if t1 <= t <= (d*dt)+t1]
        
        
        if (t2 - t1)+dt < (d*dt): # Partial trajectory for the H operator: 
            # dt = times[1]-times[0]
            n_cmpln_stamps = int(((d*dt) - (times[-1]-times[0]))/dt)
            n_stamps = int((d)/dt)
            # >>> Assigned the min/max values; for the Lipschitz monitoring, though, every value need to be computed. 
            rhos_min , rhos_max = np.repeat(rho_min,n_cmpln_stamps), np.repeat(rho_max,n_cmpln_stamps)
            # <<< 
            if formula.nf_subformula is not None: # A conjunction of predicates: 
                nf_subformula = formula.nf_subformula
                if not (nf_subformula.op in (Op.AND, Op.OR)): 
                    raise('No NF subformula is given.')
                # Compute rho at each time instance: 
                    # At each time instance we'll compute the AGM for a conjunctive formula: 
                rhos = np.array([robustness(formula = nf_subformula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # after these being computed, search if any violates the specs and compute the A or G robustness
                rhos_u = np.concatenate((rhos,rhos_max))
                rhos_l = np.concatenate((rhos,rhos_min))
                urho = min(rhos_u)
                lrho = min(rhos_l) 
                return [lrho,urho]    
            else: # If the child is a singleton (a linear predicate).  
                predFormula = copy.copy(formula)
                predFormula.op = Op.PRED
                rhos = np.array([robustness(formula = predFormula, trace=trace,times = tau,dt=dt)
                                    for tau in times],dtype=np.float64) # FIXME the predicate should be a child of the holdFormula
                rhos_u = np.concatenate((rhos,rhos_max))
                rhos_l = np.concatenate((rhos,rhos_min))
                urho = min(rhos_u)
                lrho = min(rhos_l) 
                return [lrho,urho]   
        else: #Completed trajectory   
            lrho = robustness(formula = formula, trace=trace,times = times,dt=dt)
            return [lrho,lrho]
    elif formula.op == Op.WITHIN:
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
          
        if len(times)==0 or t2 - t1 < formula.high: # For soundness, intuitively, we need long enough traces of the system  
            times = [t for t in times if t1+formula.low <= t <= t2]
            n_cmpln_stamps = int((formula.high - (times[-1]-times[0]))/dt)
            rhos_min , rhos_max = np.repeat(-float('inf'),n_cmpln_stamps), np.repeat(float('inf'),n_cmpln_stamps)
            rosis = np.array([monitor_robustness(formula = formula.child, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                  for tau in times],dtype=np.float64)
            rhos_l, rhos_u = np.concatenate((rosis[:,0],rhos_min)), np.concatenate((rosis[:,1],rhos_max))
            urho = max(rhos_u)
            lrho = max(rhos_l)
            return [lrho,urho] 
        else:
            times = [t for t in times if t1+formula.low <= t <= t2] # Recall that t2 < t1+formula.high
            rhos = np.array([robustness(formula = formula.child, trace=trace,times =  
                                                  times[np.where(np.logical_and(times>=tau,times<=t1+formula.high))],dt=dt)
                                                  for tau in times if np.any(np.logical_and(times>=tau,times<=t1+formula.high))],dtype=np.float64)
            # if np.any(np.logical_and(times>=tau,times<=t1+formula.high))
            lrho = max(rhos)
            return [lrho,lrho]
       
    elif formula.op in (Op.AND, Op.OR):
        rosis = np.array([monitor_robustness(formula=child, trace=trace, times=times,dt = dt)
                        for child in [formula.left, formula.right]],dtype=np.float64)
        rhos_l, rhos_u = rosis[:,0], rosis[:,1]
        if formula.op == Op.OR: 
            urho = max(rhos_u)
            lrho = max(rhos_l)
        else: 
            urho = min(rhos_u)
            lrho = min(rhos_l)
        return [lrho,urho]
    elif formula.op == Op.CONCAT: 
        times = list(times)
        eta_min = float('-inf')
        eta_max = float('inf')
        if t1 is None and t2 is None:
            t1,t2 = times[0],times[-1]
        true_time1 = np.array(times) >= formula.left.bounds_vls[0]
        true_time2 = np.array(times) < t2-formula.right.bounds_vls[0]
        if not np.any(np.logical_and(true_time1,true_time2)):
            rosis_1 = np.array([monitor_robustness(formula = formula.left, trace=trace,
                                times = times[np.where(np.logical_and(times>=t1,times<=tau))]
                                ,dt=dt) for tau in times])
            # The completion for the 2nd subformula
            etas_min , etas_max = np.repeat(eta_min,len(rosis_1[:,0])), np.repeat(eta_max,len(rosis_1[:,0]))
            rosis_conl = np.array([min(np.array([rosis_1[i,0],etas_min[i]])) for i in range(rosis_1.shape[0])])
            rosis_conu = np.array([min(np.array([rosis_1[i,1],etas_max[i]]))for i in range(rosis_1.shape[0])])
            rosi = [max(rosis_conl), max(rosis_conu)]
            return rosi
        
        else: 
            rosis_t = np.array([(monitor_robustness(formula = formula.left, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=t1,times<=tau))],dt=dt),
                            monitor_robustness(formula = formula.right, trace=trace,times =  
                                                    times[np.where(np.logical_and(times>=tau+dt,times<=t2))],dt=dt)) \
                                                        for tau in times[0:-1]],dtype=np.float64)
            
            rosis_conl = np.array([min(np.array([rosis_t[i,0,0],rosis_t[i,1,0]])) for i in range(rosis_t.shape[0])])
            rosis_conu = np.array([min(np.array([rosis_t[i,0,1],rosis_t[i,1,1]])) for i in range(rosis_t.shape[0])])
            rosi = [max(rosis_conl),max(rosis_conu)]
            return rosi
    else: 
        raise('the provided operator is not implementable')
    
#------------------------------------------
# ast = twtl_dfa.tree 
# The following two classes are to make traces cleaner: 
class Trace(object):
    '''Representation of a bounded system trace.

    Supports both interpolated multi-point signals and singleton observations.
    Mirrors the Trace / BoundedTrace classes in PyTeLo's stl.py / agm.py.

    Parameters
    ----------
    variables   : iterable of str   — signal variable names
    timePoints  : np.ndarray        — time stamps
    data        : iterable of array — one array per variable
    bounds      : dict              — {variable: (lo, hi)} for normalization
    kind        : str               — interpolation kind (default 'nearest')
    '''

    def __init__(self, variables, timePoints, data, bounds, kind='nearest'):
        if np.asarray(timePoints).size == 1:
            # Singleton observation — store the raw scalar directly.
            self.data = {var: val
                         for var, val in zip(variables, data)}
        else:
            self.data = {var: interp1d(timePoints, var_data, kind=kind)
                         for var, var_data in zip(variables, data)}
        self.bounds = bounds

    def value(self, variable, t):
        '''Returns the value of the signal component at time t.'''
        v = self.data[variable]
        return v(t) if callable(v) else v

    def values(self, variable, timepoints):
        '''Returns values of the signal component at each time in timepoints.'''
        v = self.data[variable]
        return v(np.asarray(timepoints)) if callable(v) else v

    def range(self, variable):
        '''Returns hi - lo normalization range for the given variable.'''
        lo, hi = self.bounds[variable]
        return hi - lo

    def number_signals(self):
        return 1

    def __str__(self):
        raise NotImplementedError


class TraceBatch(object):
    '''Representation of a batch of system traces sharing common time points.

    Mirrors TraceBatch in PyTeLo's stl.py.

    Parameters
    ----------
    variables  : iterable of str
        Signal variable names.
    timePoints : iterable of float
        Common time stamps for all signals.
    data       : iterable of lists
        Each element is a list of per-variable arrays for one signal instance.
    kind       : str
        Interpolation kind passed to scipy.interpolate.interp1d (default 'nearest').
    '''

    def __init__(self, variables, timePoints, data, kind='nearest'):
        self.no_signals = len(data)
        self.data = {}
        for k, variable in enumerate(variables):
            var_data = np.array([d[k] for d in data])
            self.data[variable] = interp1d(timePoints, var_data, kind=kind)

    def value(self, variable, t):
        '''Returns the value of the signal component at time t.'''
        return self.data[variable](t)

    def values(self, variable, timepoints):
        '''Returns the values of the signal component at each time in timepoints.'''
        return self.data[variable](np.asarray(timepoints))

    def number_signals(self):
        return self.no_signals

    def __str__(self):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Backward-compatible aliases for renamed functions
# (remove these once all call sites are updated)
# ---------------------------------------------------------------------------
powermean_robustness = agm_robustness
mntrng_agm           = monitor_agm
mntrng_agm_rt        = monitor_agm_rt
inc_mntrng_agm       = incremental_monitor_agm
mntrng_rho           = monitor_robustness


if __name__ == '__main__':
    import matplotlib.pyplot as plt  # only needed for the test/demo block

# Ahmad Testing Example: 
    

    testing_case = 'test_inc_singleObs'
    # testing_case = 'test_inc_wordObs'
    # testing_case = 'test_NnInc_singleObs'
    # ^^^^^^^^^ Testing Examples ^^^^^^^^^^^
    formula_case = 'WITHIN_operator'
    # formula_case = 'CAT_withins_operator'
    if testing_case is 'test_inc_singleObs': 
        # ********************************************
        # Debugging the case of single observation

        if formula_case is 'CAT_operator':
            # \/\/\/\/  Formula 1 Testing the CAT operator \/\/\/\/   
            twtl_formulaPred = 'H^3 s>1 . H^6 s<2'
        elif formula_case is 'WITHIN_operator': 
            # \/\/\/\/  Formula 2 Testing the within operator \/\/\/\/
            twtl_formulaPred = '[H^3 s>1]^[2,15]'
        elif formula_case is 'CAT_withins_operator':
            twtl_formulaPred = '[[H^2 s<1]^[0,4].[H^3 s>1]^[0,8]]^[0,20]' # TODO [sanity check] .[H^3 s>1]^[3,8]] time traj 
        
        
        lexerP = twtlLexer(InputStream(twtl_formulaPred))
        tokensP = CommonTokenStream(lexer=lexerP)
        parserP = twtlParser(tokensP)
        phiP = parserP.formula()
        twtl_astP =  TWTLAbstractSyntaxTreeExtractor().visit(phiP)

        s1 = np.linspace(.2,.2,3)
        t_traj1= np.linspace(0,2,3)
        
        s2 = np.linspace(1.5,1.5,3)
        t_traj2 = np.linspace(3,5,3)

        s3 = np.linspace(1.8,1.8,17)
        t_traj3 = np.linspace(6,23,17)

        # - - -- - - - -- 
        s4 = np.linspace(1.8,1.8,17)
        t_traj4 = np.linspace(6,23,17)

        s5 = np.linspace(1.8,1.8,17)
        t_traj5 = np.linspace(6,23,17)

        s6 = np.linspace(1.8,1.8,17)
        t_traj7 = np.linspace(6,23,17)


        plt.ylim((0,3))
        plt.scatter(t_traj1,s1)
        plt.scatter(t_traj2,s2)
        plt.scatter(t_traj3,s3)
        varnames = ['s']
        data_bounds = {'s': (0, 8)}
        plt.show()

        trace1 = Trace(variables=varnames,timePoints=t_traj1,data=[s1],bounds=data_bounds)
        trace2 = Trace(variables=varnames,timePoints=t_traj2,data=[s2],bounds=data_bounds)
        trace3 = Trace(variables=varnames,timePoints=t_traj3,data=[s3],bounds=data_bounds)
        tracevs = [trace1,trace2,trace3]
        ss = np.concatenate((np.concatenate((s1,s2)),s3))
        # rosi_in_d = [-0.25, 0.41161313836762536]
        # rosi_in_d = [-0.25, -0.1161313836762536]
        rosi_prev = [-1,-.1]
        rosi = [] 
        rosis = []
        for i in range(23):
            # An observation trace:  
            obs = Trace(variables=varnames,timePoints= np.array([i+1]) , data=[ss[i]],bounds=data_bounds)
            # rosi at the single observation: 
            rosi = inc_monitor_agm(formula = twtl_astP, 
                                  times = np.array([i]),
                                  trace = obs,
                                  pos_order = 0, 
                                  neg_order = 1,
                                  dt = 1,
                                  rosi_prev = rosi, 
                                  rt_mntrg_flg = False,
                                  ts = 0)
            rosis.append(rosi)    

        a = 1
        # Plotting the rosis: 
        rosis_arr = np.array(rosis)
        time_steps = np.linspace(0,len(rosis)-1,len(rosis))
        plt.scatter(time_steps,rosis_arr[:,1])
        plt.scatter(time_steps,rosis_arr[:,0])
        plt.show()
        a = 1 
                # (formula = twtl_astP, times = np.array([t_traj[i]]) ,trace = o,tp_end = t_traj[-1]
                #             ,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1,rosi_in = rosi_in,rosi_prev = twtl_astP.rosi_eta, rt_mntrg_flg = False,ts = 0)

        



        # ********************************************
    else: 
        #Where I left off: 
        twtl_formulaPred = 'H^3 s>1 . H^6 s<2'
        
        # twtl_formulaPred = 'H^10 s>1 && s<8'
        # twtl_formulaPred = '[H^10 s>1 && s<8]^[0,10]'

        #Create the AST of the predicated formula (in NFs):     
        lexerP = twtlLexer(InputStream(twtl_formulaPred))
        tokensP = CommonTokenStream(lexer=lexerP)
        parserP = twtlParser(tokensP)
        phiP = parserP.formula()
        twtl_astP =  TWTLAbstractSyntaxTreeExtractor().visit(phiP)
        # alphabetPrds  =  twtl_astP.propositions(oset([]))  # FIXME given that the propositions are defined as a conjunction of linear predicates
        # alphabetPrds = list(alphabetPrds)



        # Testing the incremental monitoring for the within operator: 
        s1 = np.linspace(.2,.2,3)
        t_traj1= np.linspace(0,2,3)
        
        s2 = np.linspace(1.5,1.5,3)
        t_traj2 = np.linspace(3,5,3)

        s3 = np.linspace(1.8,1.8,17)
        t_traj3 = np.linspace(6,23,17)

        plt.ylim((0,3))
        plt.scatter(t_traj1,s1)
        plt.scatter(t_traj2,s2)
        plt.scatter(t_traj3,s3)
        varnames = ['s']
        data_bounds = {'s': (0, 8)}
        # plt.show()

        trace1 = Trace(variables=varnames,timePoints=t_traj1,data=[s1],bounds=data_bounds)
        trace2 = Trace(variables=varnames,timePoints=t_traj2,data=[s2],bounds=data_bounds)
        trace12 = Trace(variables=varnames,timePoints=np.concatenate((t_traj1,t_traj2)),data=[np.concatenate((s1,s2))],bounds=data_bounds)
        trace3 = Trace(variables=varnames,timePoints=t_traj3,data=[s3],bounds=data_bounds)
        trace23 = Trace(variables=varnames,timePoints=t_traj3,data=[s3],bounds=data_bounds)
        trace123 = Trace(variables=varnames,timePoints=np.concatenate((t_traj1,t_traj2,t_traj3)),data=[np.concatenate((s1,s2,s3))],bounds=data_bounds)
        rosi_in = [-0.25, 0.41161313836762536]
        rosi_in = [-0.25, -0.1161313836762536]
        rosi_prev = [-1,-.1]
        
        # Testing the incremental monitor with a single observation at a time: 
        s = np.linspace(.2,.2,3)
        t_traj = np.linspace(0,2,3)
        # s = .1
        # t_traj = np.array([0.])
        rosi_in = [-0.25, 0.41161313836762536]
        for i in range(3):
            # An observation trace: 
            # o = Trace(variables=varnames,timePoints=np.array(t_traj[i:2]),data=[np.array(s[i:2])],bounds=data_bounds) 
            o = Trace(variables=varnames,timePoints=np.array([t_traj[i]]),data=[np.array([s[i]])],bounds=data_bounds) 
            rosi = monitor_agm_rt(formula = twtl_astP, times = np.array([t_traj[i]]) ,trace = o,tp_end = t_traj[-1]
                            ,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1,rosi_in = rosi_in,rosi_prev = twtl_astP.rosi_eta, rt_mntrg_flg = False,ts = 0)
        

        #<<<<<<<
        



        rosi = monitor_agm_rt(formula = twtl_astP, times = np.concatenate((t_traj1,t_traj2)) ,trace = trace12,tp_end = t_traj2[-1]
                            ,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1,rosi_in = rosi_in,rosi_prev = rosi_prev, rt_mntrg_flg = False,ts = 0)
        
        rosi_in_dum0 = monitor_agm(formula = twtl_astP, times = np.concatenate((t_traj1,t_traj2)) ,trace = trace12
                            ,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1)
        rosi_in = monitor_agm(formula = twtl_astP, times = t_traj1,trace = trace1,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1)
        rosi_in_dum1 = monitor_agm_rt(formula = twtl_astP, times = np.concatenate((t_traj1,t_traj2)) ,trace = trace12,tp_end = t_traj2[-1]
                            ,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1,rosi_in = rosi_in, rt_mntrg_flg = False,ts = 0)
        rosi_in_dum2 = monitor_agm_rt(formula = twtl_astP, times = np.concatenate((t_traj1,t_traj2)) ,trace = trace12,tp_end = t_traj2[-1]
                            ,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1,rosi_in = None, rt_mntrg_flg = True,ts = 0)
        rosi_in_dum3 = monitor_agm_rt(formula = twtl_astP, times = t_traj2 ,trace = trace2,tp_end = t_traj2[-1]
                            ,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1,rosi_in = rosi_in, rt_mntrg_flg = True,ts = 0)
        eta = agm_robustness(formula = twtl_astP,times = np.concatenate((t_traj1,t_traj2)),trace = trace12,dt = 1) 
        # rosi_in = [-0.14285714285714285, 0.4339077598104135]
        rosi = monitor_agm_rt(formula = twtl_astP, times = t_traj3 ,trace = trace3, tp_end = t_traj3[-1],
                    t1=None,t2=None, pos_order=0, neg_order=1,
                    dt = 1, rosi_in = rosi_in, rt_mntrg_flg = True,t0 = 0)
        rosi_in_ = monitor_agm(formula = twtl_astP, times = np.concatenate((t_traj1,t_traj2,t_traj3)) ,trace = trace123
                        ,t1=None,t2=None, pos_order=0, neg_order=1,dt = 1)

        
        a = 1


    # Test the rois with determinstic trajectory: 
        #XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        s1 = np.linspace(5,5,5)
        s2 = np.array([4,3,3,3])
        s3 = np.linspace(1,1,6)
        
        straj = np.concatenate((s1,s2,s3))
        straj = np.concatenate((np.linspace(2,2,3),np.linspace(1.5,1.5,3),np.linspace(1.8,1.8,17)))
        t_traj = np.linspace(0,22,23)

        # Plot the signals:
        # plt.xlim((0,3))
        plt.ylim((0,3))
        plt.scatter(t_traj,straj)
        varnames = ['s']
        data_bounds = {'s': (0, 8)}
        trace = Trace(variables=varnames,timePoints=t_traj,data=[straj],bounds=data_bounds)
        # formula,traj,times,t1=None,t2=None,trace_test = None
        # robustness
        
        # rosi_ = monitor_agm(formula = twtl_astP,times = t_traj,trace = trace)
        rho = robustness(formula = twtl_astP,times = t_traj,trace = trace, dt = 1.) 
        eta  = agm_robustness(formula = twtl_astP,times = t_traj,trace = trace,dt = 1.) 
        # Return the robustness intevals: 
        for i in range(22):
            si = straj[0:23-i]
            ti = t_traj[0:23-i]
            trace_ = Trace(variables=varnames,timePoints=ti,data=[si],bounds=data_bounds)
            rosi_ = monitor_agm(formula = twtl_astP,times = ti,trace = trace_,dt = 1.)
            rosi_ = monitor_robustness(formula = twtl_astP,times = ti,trace = trace_,dt = 1.)    
            print(rosi_)
        a = 1

        
        
        
        
        
        
        # Test the rois with determinstic trajectory: 
        #XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        x1l1 = np.linspace(0,1,10)
        x1l2 = np.linspace(1.1,1.8,10)
        x1l3 = np.linspace(1.9,1.95,3) 
        x1l4 = np.linspace(2,2.9,10)
        x1l5 = np.linspace(3,3.5,10)
        x1l6 = np.linspace(3.6,3.9,10)
        x1l7 = np.linspace(3.9,3.1,10)
        x1traj = np.concatenate((x1l1,x1l2,x1l3,x1l4,x1l5,x1l6,x1l7))
        x1traj = np.concatenate((x1l1,x1l2,x1l3,x1l4))

        x2l1 = np.linspace(0,0,10)
        x2l2 = np.linspace(0,0,10)
        x2l3 = np.linspace(0,1.5,3) 
        x2l4 = np.linspace(1.5,2,10)
        x2l5 = np.linspace(2,2,10)
        x2l6 = np.linspace(2,3,10)
        x2l7 = np.linspace(3,3,10)

        x2traj = np.concatenate((x2l1,x2l2,x2l3,x2l4,x2l5,x2l6,x2l7)) 
        x2traj = np.concatenate((x2l1,x2l2,x2l3,x2l4))  
        t_traj = np.linspace(0,6.3,63)
        t_traj = np.linspace(0,3.3,33)
        
        varnames = ['x1','x2']
        data_bounds = {'x1': (-5, 5), 'x2': (-5, 5)}
        trace = Trace(variables=varnames,timePoints=t_traj,data=[x1traj,x2traj],bounds=data_bounds)
        # formula,traj,times,t1=None,t2=None,trace_test = None
        # robustness
        
        # rosi_ = monitor_agm(formula = twtl_astP,times = t_traj,trace = trace)
        eta  = agm_robustness(formula = twtl_astP,times = t_traj,trace = trace,dt=1.) 
        a = 1





















    # > <> <> <> <> <> <> <> <> <> <><
    #      print translate('[H^3 !A]^[0, 8] * [H^2 B & [H^4 C]^[3, 9]]^[2, 19]',
    #                     kind=DFAType.Normal, norm=True)
        # twtl_formula = '(H^2 x>=6) . (H^2 x<=4) . [H^2 x>=5]^[10,12]'
        # twtl_formula = 'H^10 y>=16 && H^5 x>=10'
        # # twtl_formula = '(H^2 x>=6) . (H^2 x<=4) . (H^5 x>=5)'
        # # twtl_formula = '[H^2 x>=5]^[3,12]'
        # lexer = twtlLexer(InputStream(twtl_formula))
        # tokens = CommonTokenStream(lexer=lexer)
        # parser = twtlParser(tokens)
        # t = parser.formula()
        # # res = translate(twtl_formula,
        # #                 kind=DFAType.Infinity, norm=True)
        # traj = [7,7,7,2,2,2,3,4,5,6,6,6,6]
        # # traj = [7,7,7,7,7,7,7,7,6,6,6,6,6,6,6,10,10,10,10,10,10,10] # rho = 1, -inf
        # # traj = [4,4,4,5,8,8,8,4,6,6,6,6,6,6,6] # rho = -4
        # times = [1,2,3,4,5,6,7,8,9,10,11,12,13,14]
        

        # varnames = ['x1', 'x2']
        # data = [[7,7,7,2,2,2,3,4,5,6,6,6,6], [17,17,17,12,12,12,13,14,15,16,16,16,16],[27,27,27,22,22,22,23,24,25,26,26,26,26]]
        # timepoints = [1,2,3,4,5,6,7,8,9,10,11,12,13]
        # data_bounds = {'x1': (-5, 5), 'x2': (-5, 5)}
        # s = Trace(varnames, timepoints, data,bounds=data_bounds)

        # formula = TWTLAbstractSyntaxTreeExtractor().visit(t)
        # rho = robustness(formula=formula,traj= traj,times=times,trace_test=s)
        # a = 1
        # print(res)
        # print(res[1].g.nodes())
