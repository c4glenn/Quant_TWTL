# Copyright (c) 2024 Ahmad Ahmad <ahmadgh@bu.edu>, Cristian-Ioan Vasile <cvasile@lehigh.edu>
# SPDX-License-Identifier: MIT
'''
.. module:: twtl_ast.py
   :synopsis: TWTL Abstract Syntax Tree — formula nodes and parser bridge.

.. moduleauthor:: Cristian Ioan Vasile <cvasile@lehigh.edu>
.. moduleauthor:: Ahmad Ahmad <ahmadgh@bu.edu>
'''

from antlr4 import InputStream, CommonTokenStream

from twtlLexer import twtlLexer
from twtlParser import twtlParser
from twtlVisitor import twtlVisitor
from ordered_set import OrderedSet as oset


class Operation(object):
    '''TWTL logical and temporal operations.'''
    NOP, NOT, OR, AND, HOLD, CONCAT, WITHIN, PRED = range(8)
    opnames    = [None, '!', '||', '&&', 'H', '.', 'W', 'predicate']
    opcodes    = {'!': NOT, '&&': AND, '||': OR,
                  'H': HOLD, '.': CONCAT, 'W': WITHIN}
    opstrnames = [None, 'not', 'or', 'and', 'hold', 'concat', 'within',
                  'predicate']

    @classmethod
    def getCode(cls, text):
        '''Gets the integer code corresponding to the operator string.'''
        return cls.opcodes.get(text, cls.NOP)

    @classmethod
    def getString(cls, op):
        '''Gets the short symbol for an operation code.'''
        return cls.opnames[op]

    @classmethod
    def getName(cls, op):
        '''Gets the long descriptive name for an operation code.'''
        return cls.opstrnames[op]


class RelOperation(object):
    '''Predicate relationship (comparison) operations.

    Mirrors RelOperation in PyTeLo's stl.py so that TWTL predicates can be
    handled uniformly alongside STL predicates.
    '''
    NOP, LT, LE, GT, GE, EQ, NQ = range(7)
    opnames = [None, '<', '<=', '>', '>=', '=', '!=']
    opcodes = {'<': LT, '<=': LE, '>': GT, '>=': GE, '=': EQ, '!=': NQ}
    # Negation closure: negating a relation gives its complement.
    negop = (NOP, GE, GT, LE, LT, NQ, EQ)
    # Inverse closure: swapping sides of the predicate.
    invop = (NOP, GT, GE, LT, LE, EQ, NQ)

    @classmethod
    def getCode(cls, text):
        '''Gets the integer code for the given relation string.'''
        return cls.opcodes.get(text, cls.NOP)

    @classmethod
    def getString(cls, rop):
        '''Gets the string symbol for a relation code.'''
        return cls.opnames[rop]


class TWTLFormula(object):
    '''Abstract Syntax Tree node for a TWTL formula.

    Pure structural data — no mutable monitoring state.
    Use TWTLMonitor for incremental monitoring bookkeeping.

    Keyword arguments per operation
    --------------------------------
    AND / OR / CONCAT  : left, right  (TWTLFormula)
    NOT                : child  (TWTLFormula)
    HOLD               : duration, proposition, negated, predicate,
                         relation (RelOperation.*), variable, threshold,
                         nf_subformula
    WITHIN             : low, high (int), child (TWTLFormula)
    PRED               : predicate, relation (RelOperation.*),
                         variable, threshold
    '''

    def __init__(self, operation, **kwargs):
        self.op         = operation
        self.props      = []
        self.bounds_vls = None

        if self.op in (Operation.AND, Operation.OR, Operation.CONCAT):
            self.left  = kwargs['left']
            self.right = kwargs['right']
        elif self.op == Operation.NOT:
            self.child = kwargs['child']
        elif self.op == Operation.HOLD:
            self.duration      = kwargs['duration']
            self.proposition   = kwargs['proposition']
            self.negated       = kwargs['negated']
            self.predicate     = kwargs['predicate']
            self.relation      = kwargs['relation']      # RelOperation code
            self.variable      = kwargs['variable']
            self.threshold     = kwargs['threshold']
            self.nf_subformula = kwargs['nf_subformula']
        elif self.op == Operation.WITHIN:
            self.low   = kwargs['low']
            self.high  = kwargs['high']
            self.child = kwargs['child']
        elif self.op == Operation.PRED:
            self.predicate = kwargs['predicate']
            self.relation  = kwargs['relation']          # RelOperation code
            self.variable  = kwargs['variable']
            self.threshold = kwargs['threshold']

        self.__string = None
        self.__hash   = None

    # ------------------------------------------------------------------
    # Structural queries
    # ------------------------------------------------------------------

    def bounds(self):
        '''Computes the (lower, upper) time bounds of the TWTL formula.

        Returns [lower_bound, upper_bound].
        '''
        if self.op == Operation.AND:
            lb, rb = self.left.bounds(), self.right.bounds()
            self.bounds_vls = [max(lb[0], rb[0]), max(lb[1], rb[1])]
        elif self.op == Operation.OR:
            lb, rb = self.left.bounds(), self.right.bounds()
            self.bounds_vls = [min(lb[0], rb[0]), max(lb[1], rb[1])]
        elif self.op == Operation.NOT:
            self.bounds_vls = self.child.bounds()
        elif self.op == Operation.HOLD:
            self.bounds_vls = [self.duration, self.duration]
        elif self.op == Operation.CONCAT:
            lb, rb = self.left.bounds(), self.right.bounds()
            self.bounds_vls = [1 + lb[0] + rb[0], 1 + lb[1] + rb[1]]
        elif self.op == Operation.WITHIN:
            cb = self.child.bounds()
            assert cb[0] <= self.high - self.low, \
                'Child formula is unfeasible within the given time window'
            self.bounds_vls = [self.low + cb[0], self.high]
        elif self.op == Operation.PRED:
            self.bounds_vls = [0, 0]
        return self.bounds_vls

    def variables(self):
        '''Returns the set of signal variable names referenced in the formula.

        Mirrors STLFormula.variables() in PyTeLo's stl.py.
        '''
        if self.op == Operation.PRED:
            return {self.variable} if self.variable is not None else set()
        elif self.op == Operation.HOLD:
            if self.variable is not None:
                return {self.variable}
            elif self.nf_subformula is not None:
                return self.nf_subformula.variables()
            return set()
        elif self.op in (Operation.AND, Operation.OR, Operation.CONCAT):
            return self.left.variables() | self.right.variables()
        elif self.op in (Operation.NOT, Operation.WITHIN):
            return self.child.variables()
        return set()

    def propositions(self, props):
        '''Returns the set of atomic propositions / predicate nodes.

        Used internally by the DFA translation layer.
        For signal variable names prefer variables().
        '''
        if self.op == Operation.HOLD:
            if self.proposition is None and self.predicate is not None:
                return self
            elif self.proposition is not None:
                props.add(self.proposition)
                return props
            else:
                props.add(self.nf_subformula)
                return props
        elif self.op in (Operation.AND, Operation.OR, Operation.CONCAT):
            lp = self.left.propositions(set())
            rp = self.right.propositions(set())
            for p in (lp if isinstance(lp, set) else [lp]):
                props.add(p)
            for p in (rp if isinstance(rp, set) else [rp]):
                props.add(p)
            return props
        elif self.op in (Operation.NOT, Operation.WITHIN):
            return self.child.propositions(set())

    # ------------------------------------------------------------------
    # Identity / hashing
    # ------------------------------------------------------------------

    def identifier(self):
        h = hash(self)
        if h < 0:
            return hex(ord('-'))[2:] + hex(-h)[1:]
        return hex(ord('+'))[2:] + hex(h)[1:]

    def __hash__(self):
        if self.__hash is None:
            self.__hash = hash(str(self))
        return self.__hash

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        if self.__string is not None:
            return self.__string

        opname = Operation.getString(self.op)
        if self.op in (Operation.AND, Operation.OR, Operation.CONCAT):
            s = '{left} {op} {right}'.format(
                left=self.left, op=opname, right=self.right)
        elif self.op == Operation.NOT:
            s = '{op} {child}'.format(op=opname, child=self.child)
        elif self.op == Operation.HOLD:
            if self.proposition is not None:
                prop = ('!' if self.negated else '') + str(self.proposition)
            elif self.variable is not None:
                prop = '{v} {rel} {th}'.format(
                    v=self.variable,
                    rel=RelOperation.getString(self.relation),
                    th=self.threshold)
            else:
                prop = str(self.nf_subformula)
            s = '{op}^{d} {prop}'.format(op=opname, d=self.duration, prop=prop)
        elif self.op == Operation.WITHIN:
            s = '[{child}]^[{low}, {high}]'.format(
                child=self.child, low=self.low, high=self.high)
        elif self.op == Operation.PRED:
            s = '({v} {rel} {th})'.format(
                v=self.variable,
                rel=RelOperation.getString(self.relation),
                th=self.threshold)
        else:
            s = '<unknown op {}>'.format(self.op)

        self.__string = s
        return self.__string


# ---------------------------------------------------------------------------
# Parse-tree visitor — builds the AST from an ANTLR parse tree
# ---------------------------------------------------------------------------

class TWTLAbstractSyntaxTreeExtractor(twtlVisitor):
    '''Parse-tree visitor that constructs the AST of a TWTL formula.

    Mirrors STLAbstractSyntaxTreeExtractor in PyTeLo's stl.py.
    '''

    def visitFormula(self, ctx):
        if ctx.op is None:
            op = Operation.PRED
        elif ctx.op.text == '(':
            op = Operation.NOP
        elif ctx.op.text == '[':
            op = Operation.WITHIN
        else:
            op = Operation.getCode(ctx.op.text)

        if op == Operation.PRED:
            pred           = ctx.children[0]
            pred_variable  = pred.children[0].children[0].symbol.text
            pred_relation  = RelOperation.getCode(pred.children[1].symbol.text)
            pred_threshold = float(pred.children[2].children[0].symbol.text)
            return TWTLFormula(op,
                               predicate=pred,
                               relation=pred_relation,
                               variable=pred_variable,
                               threshold=pred_threshold,
                               proposition=None,
                               nf_subformula=None)

        elif op in (Operation.AND, Operation.OR, Operation.CONCAT):
            return TWTLFormula(op,
                               left=self.visitFormula(ctx.left),
                               right=self.visitFormula(ctx.right))

        elif op == Operation.NOT:
            return TWTLFormula(op, child=self.visit(ctx.child))

        elif op == Operation.HOLD:
            duration  = 0 if ctx.duration is None else int(ctx.duration.text)
            singleton = len(ctx.children[3].children) == 1
            if singleton:
                is_pred = len(ctx.children[3].children[0].children) == 3
                if is_pred:
                    pred           = ctx.children[3].children[0]
                    pred_variable  = pred.children[0].children[0].symbol.text
                    pred_relation  = RelOperation.getCode(
                                         pred.children[1].symbol.text)
                    pred_threshold = float(
                                         pred.children[2].children[0].symbol.text)
                    return TWTLFormula(op,
                                       duration=duration,
                                       predicate=pred,
                                       relation=pred_relation,
                                       variable=pred_variable,
                                       threshold=pred_threshold,
                                       proposition=None,
                                       nf_subformula=None,
                                       negated=ctx.negated is not None)
                else:   # atomic proposition
                    prop = ctx.children[3].children[0].children[0].symbol.text
                    if prop in ('true', 'false'):
                        prop = (prop == 'true')
                    return TWTLFormula(op,
                                       duration=duration,
                                       predicate=None,
                                       relation=None,
                                       variable=None,
                                       threshold=None,
                                       proposition=prop,
                                       nf_subformula=None,
                                       negated=ctx.negated is not None)
            else:   # normal form (CNF / DNF of predicates)
                op_sub = Operation.getCode(ctx.children[3].op.text)
                nf_sub = TWTLFormula(op_sub,
                                     left=self.visitFormula(ctx.children[3].left),
                                     right=self.visitFormula(ctx.children[3].right))
                return TWTLFormula(op,
                                   duration=duration,
                                   predicate=None,
                                   relation=None,
                                   variable=None,
                                   threshold=None,
                                   proposition=None,
                                   nf_subformula=nf_sub,
                                   negated=ctx.negated is not None)

        elif op == Operation.WITHIN:
            low  = int(ctx.low.text)
            high = int(ctx.high.text)
            return TWTLFormula(Operation.WITHIN,
                               child=self.visitFormula(ctx.child),
                               low=low, high=high)

        elif op == Operation.NOP:
            return self.visitFormula(ctx.child)

        else:
            raise ValueError('Unknown TWTL operation: {!r}'.format(ctx.op.text))


# ---------------------------------------------------------------------------
# Public helper — mirrors stl.to_ast() in PyTeLo
# ---------------------------------------------------------------------------

def to_ast(formula: str) -> TWTLFormula:
    '''Parses a TWTL formula string and returns its Abstract Syntax Tree.

    Mirrors to_ast() in PyTeLo's stl.py.

    Parameters
    ----------
    formula : str
        TWTL formula string, e.g. ``"H^3 s>1 . [H^2 s<5]^[0,8]"``.

    Returns
    -------
    TWTLFormula
        Root node of the parsed AST.

    Examples
    --------
    >>> ast = to_ast('H^3 s>1 . [H^2 s<5]^[0,8]')
    >>> ast.bounds()
    [4, 12]
    >>> ast.variables()
    {'s'}
    '''
    lexer  = twtlLexer(InputStream(formula))
    tokens = CommonTokenStream(lexer)
    parser = twtlParser(tokens)
    phi    = parser.formula()
    return TWTLAbstractSyntaxTreeExtractor().visit(phi)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    test_formula = 'H^3 s>1 . [H^2 s<5]^[0,8]'
    ast = to_ast(test_formula)
    print('Formula  :', test_formula)
    print('AST      :', str(ast))
    print('Bounds   :', ast.bounds())
    print('Variables:', ast.variables())
