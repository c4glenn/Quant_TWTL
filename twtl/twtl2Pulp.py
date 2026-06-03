from typing import Dict, Tuple, Optional, Any
import copy
import logging

import pulp

from twtl.twtl_ast import TWTLFormula, Operation, RelOperation

logger = logging.getLogger(__name__)
class TWTL2PuLP():
    def __init__(self, formula: TWTLFormula, 
                 ranges: Dict[str, Tuple[int | float, int | float]], 
                 vtypes: Optional[Dict[str, Any]] = None,
                 model: Optional[pulp.LpProblem] = None,
                 robust: bool = False,
                 solver_name: str = 'SCIP',
                 int_rho:bool = False) -> None:
        self.formula = formula
        self.M = 1000
        self.ranges = ranges
        self.solver_name = solver_name
        
        formula_vars = formula.variables()
        range_vars = set(self.ranges.keys())
        assert formula_vars <= range_vars, f"Missing ranges for variables: {formula_vars - range_vars}"
        
        if robust and 'rho' not in self.ranges:
            self.ranges['rho'] = (-1e6, self.M - 1)
        
        self.vtypes = vtypes if vtypes is not None else {}
        for v in self.ranges:
            if v not in self.vtypes:
                self.vtypes[v] = 'Continuous'
            
        self.model = model
        if model is None:
            self.model = pulp.LpProblem(f"TwTL", pulp.LpMaximize)
                
        self.variables = dict()
        
        if robust:
            rho_min, rho_max = self.ranges['rho']
            if int_rho:
                self.rho = pulp.LpVariable('rho', int(rho_min), int(rho_max), cat=pulp.const.LpInteger)
            else:
                self.rho = pulp.LpVariable('rho', rho_min, rho_max)
            self.model += self.rho  # Objective: maximize robustness
        else:
            self.rho = 0
        
        self._milp_call = {
            Operation.AND: self._and,
            Operation.CONCAT: self._concat,
            Operation.HOLD: self._hold,
            Operation.OR: self._or,
            Operation.PRED: self._predicate,
            Operation.WITHIN: self._within,
            Operation.NOT: self._not,
        }

    def translate(self, satisfacation: bool = True) -> pulp.LpVariable:
        rho = self._to_milp(self.formula, t=0)
        if satisfacation:
            self.model += (self.rho == rho, "formula satisfaction") # pyright: ignore[reportOperatorIssue]
        return rho

    def _add_formula_variable(self, formula: TWTLFormula, t: int=0) -> Tuple[pulp.LpVariable, bool]:
        opname = Operation.getName(formula.op)
        identifier = formula.identifier()
        name = f'{opname}_{identifier}'
        return self._add_bool(name, t)

    def _add_bool(self, name: str, t: int) -> Tuple[pulp.LpVariable, bool]:
        if name not in self.variables:
            self.variables[name] = {}
        
        if t not in self.variables[name]:
            logger.debug(f"creating {name} for {t=}")
            var = pulp.LpVariable(f"{name}_{t}", cat='Binary')
            self.variables[name][t] = var
            return var, True
        return self.variables[name][t], False

    def _add_state(self, state_name, t) -> pulp.LpVariable:
        """Add a state variable at time t."""
        if state_name not in self.variables:
            self.variables[state_name] = {}
        
        if t not in self.variables[state_name]:
            if 'rho' in state_name:
                low, high = -self.M, self.M
                vtype = 'Continuous'
            else:
                low, high = self.ranges[state_name]
                vtype = self.vtypes[state_name]
            name = f'{state_name}_{t}'
            var = pulp.LpVariable(name, low, high, cat=vtype)
            self.variables[state_name][t] = var
        
        return self.variables[state_name][t]

    def _to_milp(self, formula: TWTLFormula, t:int = 0):
        if formula in self.variables and t in self.variables[formula]: 
            logger.debug(f"{formula}@{t=} is being restored from cache")
            return self.variables[formula][t]
        if formula not in self.variables:
            self.variables[formula] = dict()
        
        rho = self._milp_call[formula.op](formula, t)
        self.variables[formula][t] = rho        
        return rho
        
    def _and(self, formula: TWTLFormula, t):
        """Encode conjunction (AND)."""
        rho_internal = self._add_state(f"internal_cond_rho_{formula.identifier()}", t)
        z = self._add_formula_variable(formula, t)[0]
        # left 
        for child in [formula.left, formula.right]:
            rho = self._to_milp(child, t)
            self.model += rho_internal <= rho #I *think* this works, maximize should pull it up to be the minimum
        return rho_internal

    def _or(self, formula: TWTLFormula, t):
        """Encode disjunction (OR)."""
        rho_internal = self._add_state(f"internal_cond_rho_{formula.identifier()}", t)
        z_children = []
        for child in [formula.left, formula.right]:
            rho = self._to_milp(child, t)
            z_child = self._add_bool(f"z_{formula.identifier()}_{child.identifier()}", t)
            z_children.append(z_child)
            self.model += rho_internal >= rho, f"greater_than_child_or_{formula.identifier()}_{child.identifier()}_{t}" # pyright: ignore[reportOperatorIssue]
            self.model += rho_internal <= rho + self.M * (1 - z_child[0]), f"less_than_child_or_{formula.identifier()}_{child.identifier()}_{t}" # pyright: ignore[reportOperatorIssue]
            # bigger than all of the elements
            # smaller than one particular element selected via Z
            # since solver is maximizing it should pick the max
        self.model += pulp.lpSum([x[0] for x in z_children]) == 1, f"force_one_of_the_ors_{formula.identifier()}_{t}" # pyright: ignore[reportOperatorIssue]
        return rho_internal

    def _concat(self, formula: TWTLFormula, t):
        a, b = formula.left.bounds() # pyright: ignore[reportGeneralTypeIssues]
        c, d = formula.right.bounds()
        logger.debug(f"left formula {formula.left}")
        times = [t + tau for tau in range(a + 1, b)]
        rho_internal = self._add_state(f"internal_cond_concat_rho_{formula.identifier()}", t)
        logger.debug(f"concat {times} {a} {b} {c} {d}")
        concat_vars = []
        for time in times:
            z_choice_name = f"zz_choice_{formula.identifier()}"
            right = self._add_bool(z_choice_name, time)[0]
            y_split_name = f"y_split_{formula.identifier()}"
            total_splits = len(self.variables[z_choice_name])
            if total_splits > 1:
                split, new = self._add_bool(y_split_name, time)
                if new:
                    self.model += right >= self._add_bool(z_choice_name, time-1)[0] + 1 * (split), f"always_stay_later_{formula.identifier()}_{time}" # pyright: ignore[reportOperatorIssue] #if it has already flipped it has to stay flipped
                    self.model += right <= self._add_bool(z_choice_name, time-1)[0] + self.M * (split), f"relax_equality_when_sliding_{formula.identifier()}_{time}" # if this time is the chosen time to flip, then allow it to be not equal
            else:
                new = True
                concat_vars.append(y_split_name) # if this is the first time step, add the transition var to the list
                self.model += right == 0, f"force_first_concat_{formula.identifier()}_{time}" # pyright: ignore[reportOperatorIssue] #the concat has to start with the left option
            
            rho_inner = self._add_state(f"internal_cond_rho_inner_{formula.identifier()}", time)
            left_rho = self._to_milp(formula.left, t)
            right_rho = self._to_milp(formula.right, time)
            logger.debug(f"total_splits {total_splits} {concat_vars}")

            if new:
                self.model += rho_inner <= left_rho + self.M * right, f"equality_left_LT_{formula.identifier()}_{time}"  # pyright: ignore[reportOperatorIssue]
                self.model += rho_inner >= left_rho - self.M * right, f"equality_left_GT_{formula.identifier()}_{time}" 
                
                self.model += rho_inner <= right_rho + self.M * (1 - right), f"equality_right_LT_{formula.identifier()}_{time}" 
                self.model += rho_inner >= right_rho - self.M * (1 - right), f"equality_right_GT_{formula.identifier()}_{time}" 
                
                self.model += rho_internal <= rho_inner, f"force_rho_less_this_timestep_{formula.identifier()}_{time}" # maximizing it ?
        
        for var_name in concat_vars:
            self.model += pulp.lpSum(self.variables[var_name]) == 1, f"only_allow_one_switch_{formula.identifier()}_{t}" # pyright: ignore[reportOperatorIssue]
        concat_vars = []

        return rho_internal
    
    def _hold(self, formula: TWTLFormula, t):
        d = formula.duration
        logger.debug(f"Holding at {t=} with {d=}")
        if formula.nf_subformula:
            form = formula.nf_subformula
        else:
            form = TWTLFormula(Operation.PRED, predicate="", relation=formula.relation, variable=formula.variable, threshold=formula.threshold)
        
        rho_children = [self._to_milp(form, t+tau) for tau in range(d+1)]
        rho_internal = self._add_state(f"internal_cond_hold_rho_{formula.identifier()}", t)
        for i, rho in enumerate(rho_children):
            self.model += rho_internal <= rho, f"less_than_all_the_option_{i}_{formula.identifier()}_{t}" # pyright: ignore[reportOperatorIssue] # again i think it will pull this up to be the minimum?
        return rho_internal


    def _predicate(self, formula: TWTLFormula, t):
        assert formula.op == Operation.PRED
        rho_internal = self._add_state(f"internal_cond_predicate_rho_{formula.identifier()}", t)
        v = self._add_state(formula.variable, t)
        match formula.relation:
            case RelOperation.GT | RelOperation.GE: 
                self.model += v - formula.threshold >= rho_internal, f"predicate_GT_{formula.identifier()}_{t}" # pyright: ignore[reportOperatorIssue]
            case RelOperation.LT | RelOperation.LE: 
                self.model += formula.threshold - v >= rho_internal, f"predicate_LT_{formula.identifier()}_{t}" # pyright: ignore[reportOperatorIssue]
            case _: raise NotImplementedError(f"{formula.relation=} not implemented yet")
        return rho_internal
    
    def _not(self, formula: TWTLFormula, t):
        assert formula.op == Operation.NOT
        return - self._to_milp(formula.child, t)

    def _within(self, formula: TWTLFormula, t):
        a, b = formula.low, formula.high
        cta, ctb = formula.child.bounds()
        
        logger.debug(f"within range {t=} {range(a + cta, b - ctb)}")
        logger.debug([f"{t + tau}" for tau in range(a + cta, b - ctb + 1)])
        rho_children = [self._to_milp(formula.child, t+tau) for tau in range(a + cta, b - ctb + 1)]
        rho_internal = self._add_state(f"internal_cond_rho_{formula.identifier()}", t)
        z_children = []
        for i, rho in enumerate(rho_children):
            z_child = self._add_bool(f"z_within_{formula.identifier()}_{i}_{t}", t)
            z_children.append(z_child[0])
            self.model += rho_internal >= rho
            self.model += rho_internal <= rho + self.M * (1 - z_child[0])
            # bigger than all of the elements
            # smaller than one particular element selected via Z
            # since solver is maximizing it should pick the max
        self.model += pulp.lpSum(z_children) >= 1
        return rho_internal

    