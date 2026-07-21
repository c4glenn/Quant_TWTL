from typing import Dict, Tuple, Optional, Any
import copy
import logging

import z3

# from twtl.twtl_ast import TWTLFormula, Operation, RelOperation
from src.submodules.Quant_TWTL.twtl.twtl_ast import TWTLFormula, Operation, RelOperation

logger = logging.getLogger(__name__)

class TWTL2SMT():
    def __init__(self, formula: TWTLFormula, 
                 ranges: Dict[str, Tuple[int | float, int | float]], 
                 vtypes: Optional[Dict[str, Any]] = None,
                 solver: Optional[z3.Solver | z3.Optimize] = None,
                 optimize: bool = True,
                 ctx: Optional[z3.Context] = None,
                 int_rho:bool = False) -> None:
        self.formula = formula
        self.ranges = ranges
        self.vtypes = vtypes
        self.optimize = optimize
        self.ctx = ctx
        self.int_rho = int_rho
        if self.vtypes is None:
            self.vtypes = {v: z3.Int if self.int_rho else z3.Real for v in self.ranges}
            
        
        if 'rho' not in self.vtypes:
            if int_rho:
                self.vtypes['rho'] = z3.Int
            else:
                self.vtypes['rho'] = z3.Real
        if 'rho' not in self.ranges:
            self.ranges['rho'] = (-40, 1000)

        
        if solver is None:
            if self.optimize:
                self.solver = z3.Optimize(ctx=self.ctx)
            else:
                self.solver = z3.Solver(ctx=self.ctx)
        else:
            self.solver = solver
        
        self.variables = dict()
        self.state_vars = dict()
        
        if int_rho:
            self.rho = z3.Int('internal_cond_rho', ctx=self.ctx)
        else:
            self.rho = z3.Real('internal_cond_rho', ctx=self.ctx)
            
        self.__smt_call = {
            Operation.AND: self._and,
            Operation.CONCAT: self._concat, 
            Operation.HOLD: self._hold,
            Operation.OR: self._or,
            Operation.PRED: self._predicate,
            Operation.WITHIN: self._within,
            Operation.NOT: self._not,
        }
    
    def translate(self, satisfaction:bool = True):
        rho = self.to_smt(self.formula)
        if satisfaction:
            self.solver.add(self.rho == rho)
            if self.optimize: self.solver.maximize(self.rho) # pyright: ignore[reportAttributeAccessIssue]
        return rho
            
    def _add_state(self, state, stype, t:int=0, id=""):
        if state in self.state_vars and t in self.state_vars[state]:
            return self.state_vars[state][t]

        if state not in self.state_vars:
            self.state_vars[state] = dict()
        
        name = f"{state}_{t}{'_' if id else ''}{id if id else ''}"
        
        if stype == z3.Bool:
            self.state_vars[state][t] = z3.Bool(name, ctx=self.ctx)
            return self.state_vars[state][t]
        
        vtype = self.vtypes.get(state, stype) # pyright: ignore[reportOptionalMemberAccess]
        self.state_vars[state][t] = vtype(name, ctx=self.ctx) # pyright: ignore[reportOptionalCall]
        
        if state in self.ranges or "rho" in state:
            state_name = "rho" if "rho" in state else state
            low, high = self.ranges[state_name]
            try:
                self.solver.add(z3.And(self.state_vars[state][t] >= low, self.state_vars[state][t] <= high))
            except TypeError as error:
                logger.warning(f"type error trying to apply {self.ranges[state_name]=} onto {state=}", exc_info=True)
        else:
            logger.debug(f"{state} is unbounded")
        
        return self.state_vars[state][t]
        
        
    def to_smt(self, formula: TWTLFormula, t:int=0):
        if formula in self.variables and t in self.variables[formula]:
            return self.variables[formula][t]
        if formula not in self.variables:
            self.variables[formula] = dict()
        
        rho = self.__smt_call[formula.op](formula, t)
        self.variables[formula][t] = rho
        return rho
    
    def _and(self, formula: TWTLFormula, t):
        assert formula.op == Operation.AND
        rho = self._add_state(f"rho_{formula.identifier()}", z3.Int if self.int_rho else z3.Real, t)
        for child in [formula.left, formula.right]:
            child_rho = self.to_smt(child, t)
            self.solver.add(rho <= child_rho)
        return rho

    def _concat(self, formula: TWTLFormula, t):
        a, b = formula.left.bounds()
        c, d = formula.right.bounds()
        
        times = [t+tau for tau in range(a+1, b)]
        rho_internal = self._add_state(f"internal_cond_concat_rho_{formula.identifier()}", z3.Int if self.int_rho else z3.Real, t)
        switch_time = self._add_state(f"switch_time_{formula.identifier()}", z3.Int, t)
        self.solver.add(z3.And(switch_time >= t + a + 1, switch_time<= t + b))
        
        for time in times:
            rho_inner = self._add_state(f"internal_cond_rho_inner_{formula.identifier()}", z3.Int if self.int_rho else z3.Real, time)
            left_rho = self.to_smt(formula.left, t)
            right_rho = self.to_smt(formula.right, time)
            
            self.solver.add(z3.If(time >= switch_time, rho_inner == right_rho, rho_inner == left_rho))
            self.solver.add(rho_internal <= rho_inner)
        return rho_internal

    def _hold(self, formula: TWTLFormula, t):
        d = formula.duration
        
        if formula.nf_subformula:
            form = formula.nf_subformula
        else:
            form = TWTLFormula(Operation.PRED, predicate="", relation=formula.relation, variable=formula.variable, threshold=formula.threshold)
    
        rho_children = [self.to_smt(form, t+tau) for tau in range(d+1)]
        rho_internal = self._add_state(f"internal_cond_hold_rho_{formula.identifier()}", z3.Int if self.int_rho else z3.Real, t)
        
        for i, rho in enumerate(rho_children):
            self.solver.add(rho_internal <= rho)
        return rho_internal        
    
    def _or(self, formula: TWTLFormula, t):
        assert formula.op == Operation.OR
        rho = self._add_state(f"rho_{formula.identifier()}", z3.Int if self.int_rho else z3.Real, t)
        for child in [formula.left, formula.right]:
            child_rho = self.to_smt(child, t)
            self.solver.add(rho >= child_rho)
        self.solver.add(z3.Or([rho == x for x in [formula.left, formula.right]]))
        return rho
    
    def _predicate(self, formula: TWTLFormula, t):
        assert formula.op == Operation.PRED
        
        v = self._add_state(formula.variable, z3.Real, t)
        
        match formula.relation:
            case RelOperation.GT | RelOperation.GE: return v - formula.threshold
            case RelOperation.LT | RelOperation.LE: return formula.threshold - v
            case _: raise NotImplementedError(f"{formula.relation=} not implemented yet")


    def _within(self, formula: TWTLFormula, t):
        assert formula.op == Operation.WITHIN
        a, b = formula.low, formula.high
        cta, ctb = formula.child.bounds()
        
        rho_children = [self.to_smt(formula.child, t+tau) for tau in range(a+cta, b-ctb + 1)]
        rho_internal = self._add_state(f"internal_cond_rho_{formula.identifier()}", stype=z3.Int if self.int_rho else z3.Real, t=t)
        
        for i, rho in enumerate(rho_children):
            self.solver.add(rho_internal >= rho)
        
        self.solver.add(z3.Or([rho_internal == x for x in rho_children]))
        return rho_internal

    def _not(self, formula: TWTLFormula, t):
        assert formula.op == Operation.NOT
        return - self.to_smt(formula.child, t)
