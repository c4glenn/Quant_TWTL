# Generated from twtl.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO


license_text='''
    Copyright (C) 2015-2020  Cristian Ioan Vasile <cvasile@lehigh.edu>
    Explainable Robotics Lab (ERL), Autonomous and Intelligent Robotics Lab
    Lehigh University

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

def serializedATN():
    return [
        4,1,27,105,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,1,0,1,0,1,0,1,0,1,0,1,
        0,1,0,1,0,3,0,17,8,0,1,0,3,0,20,8,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,
        1,0,1,0,1,0,1,0,1,0,1,0,3,0,35,8,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,
        0,1,0,5,0,46,8,0,10,0,12,0,49,9,0,1,1,1,1,1,1,1,1,3,1,55,8,1,1,1,
        1,1,1,1,1,1,1,1,1,1,5,1,63,8,1,10,1,12,1,66,9,1,1,2,1,2,1,2,1,2,
        1,2,1,2,1,2,3,2,75,8,2,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,
        3,1,3,3,3,89,8,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,1,3,5,3,100,8,3,
        10,3,12,3,103,9,3,1,3,0,3,0,2,6,4,0,2,4,6,0,4,1,0,7,11,2,0,1,1,12,
        12,1,0,13,14,1,0,15,16,121,0,34,1,0,0,0,2,54,1,0,0,0,4,74,1,0,0,
        0,6,88,1,0,0,0,8,9,6,0,-1,0,9,10,5,1,0,0,10,11,3,0,0,0,11,12,5,2,
        0,0,12,35,1,0,0,0,13,14,5,20,0,0,14,15,5,3,0,0,15,17,5,22,0,0,16,
        13,1,0,0,0,16,17,1,0,0,0,17,19,1,0,0,0,18,20,5,19,0,0,19,18,1,0,
        0,0,19,20,1,0,0,0,20,21,1,0,0,0,21,35,3,2,1,0,22,23,5,19,0,0,23,
        35,3,0,0,4,24,25,5,4,0,0,25,26,3,0,0,0,26,27,5,5,0,0,27,28,5,3,0,
        0,28,29,5,4,0,0,29,30,5,22,0,0,30,31,5,6,0,0,31,32,5,22,0,0,32,33,
        5,5,0,0,33,35,1,0,0,0,34,8,1,0,0,0,34,16,1,0,0,0,34,22,1,0,0,0,34,
        24,1,0,0,0,35,47,1,0,0,0,36,37,10,6,0,0,37,38,5,21,0,0,38,46,3,0,
        0,7,39,40,10,2,0,0,40,41,5,18,0,0,41,46,3,0,0,3,42,43,10,1,0,0,43,
        44,5,17,0,0,44,46,3,0,0,2,45,36,1,0,0,0,45,39,1,0,0,0,45,42,1,0,
        0,0,46,49,1,0,0,0,47,45,1,0,0,0,47,48,1,0,0,0,48,1,1,0,0,0,49,47,
        1,0,0,0,50,51,6,1,-1,0,51,55,5,24,0,0,52,55,5,23,0,0,53,55,3,4,2,
        0,54,50,1,0,0,0,54,52,1,0,0,0,54,53,1,0,0,0,55,64,1,0,0,0,56,57,
        10,2,0,0,57,58,5,18,0,0,58,63,3,2,1,3,59,60,10,1,0,0,60,61,5,17,
        0,0,61,63,3,2,1,2,62,56,1,0,0,0,62,59,1,0,0,0,63,66,1,0,0,0,64,62,
        1,0,0,0,64,65,1,0,0,0,65,3,1,0,0,0,66,64,1,0,0,0,67,75,5,24,0,0,
        68,75,5,23,0,0,69,75,5,25,0,0,70,71,3,6,3,0,71,72,7,0,0,0,72,73,
        3,6,3,0,73,75,1,0,0,0,74,67,1,0,0,0,74,68,1,0,0,0,74,69,1,0,0,0,
        74,70,1,0,0,0,75,5,1,0,0,0,76,77,6,3,-1,0,77,78,7,1,0,0,78,79,3,
        6,3,0,79,80,5,2,0,0,80,89,1,0,0,0,81,82,5,25,0,0,82,83,5,1,0,0,83,
        84,3,6,3,0,84,85,5,2,0,0,85,89,1,0,0,0,86,89,5,22,0,0,87,89,5,25,
        0,0,88,76,1,0,0,0,88,81,1,0,0,0,88,86,1,0,0,0,88,87,1,0,0,0,89,101,
        1,0,0,0,90,91,10,6,0,0,91,92,5,3,0,0,92,100,3,6,3,6,93,94,10,4,0,
        0,94,95,7,2,0,0,95,100,3,6,3,5,96,97,10,3,0,0,97,98,7,3,0,0,98,100,
        3,6,3,4,99,90,1,0,0,0,99,93,1,0,0,0,99,96,1,0,0,0,100,103,1,0,0,
        0,101,99,1,0,0,0,101,102,1,0,0,0,102,7,1,0,0,0,103,101,1,0,0,0,12,
        16,19,34,45,47,54,62,64,74,88,99,101
    ]

class twtlParser ( Parser ):

    grammarFileName = "twtl.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "'('", "')'", "'^'", "'['", "']'", "','", 
                     "'<'", "'<='", "'='", "'>='", "'>'", "'-('", "'*'", 
                     "'/'", "'+'", "'-'", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "'H'", "'.'" ]

    symbolicNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                      "<INVALID>", "AND", "OR", "NOT", "HOLD", "CONCAT", 
                      "RATIONAL", "TRUE", "FALSE", "VARIABLE", "LINECMT", 
                      "WS" ]

    RULE_formula = 0
    RULE_nf = 1
    RULE_booleanExpr = 2
    RULE_expr = 3

    ruleNames =  [ "formula", "nf", "booleanExpr", "expr" ]

    EOF = Token.EOF
    T__0=1
    T__1=2
    T__2=3
    T__3=4
    T__4=5
    T__5=6
    T__6=7
    T__7=8
    T__8=9
    T__9=10
    T__10=11
    T__11=12
    T__12=13
    T__13=14
    T__14=15
    T__15=16
    AND=17
    OR=18
    NOT=19
    HOLD=20
    CONCAT=21
    RATIONAL=22
    TRUE=23
    FALSE=24
    VARIABLE=25
    LINECMT=26
    WS=27

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class FormulaContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.left = None # FormulaContext
            self.op = None # Token
            self.child = None # FormulaContext
            self.duration = None # Token
            self.negated = None # Token
            self.prop = None # NfContext
            self.low = None # Token
            self.high = None # Token
            self.right = None # FormulaContext

        def formula(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(twtlParser.FormulaContext)
            else:
                return self.getTypedRuleContext(twtlParser.FormulaContext,i)


        def nf(self):
            return self.getTypedRuleContext(twtlParser.NfContext,0)


        def HOLD(self):
            return self.getToken(twtlParser.HOLD, 0)

        def RATIONAL(self, i:int=None):
            if i is None:
                return self.getTokens(twtlParser.RATIONAL)
            else:
                return self.getToken(twtlParser.RATIONAL, i)

        def NOT(self):
            return self.getToken(twtlParser.NOT, 0)

        def CONCAT(self):
            return self.getToken(twtlParser.CONCAT, 0)

        def OR(self):
            return self.getToken(twtlParser.OR, 0)

        def AND(self):
            return self.getToken(twtlParser.AND, 0)

        def getRuleIndex(self):
            return twtlParser.RULE_formula

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterFormula" ):
                listener.enterFormula(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitFormula" ):
                listener.exitFormula(self)



    def formula(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = twtlParser.FormulaContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 0
        self.enterRecursionRule(localctx, 0, self.RULE_formula, _p)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 34
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,2,self._ctx)
            if la_ == 1:
                self.state = 9
                localctx.op = self.match(twtlParser.T__0)
                self.state = 10
                localctx.child = self.formula(0)
                self.state = 11
                self.match(twtlParser.T__1)
                pass

            elif la_ == 2:
                self.state = 16
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==20:
                    self.state = 13
                    localctx.op = self.match(twtlParser.HOLD)
                    self.state = 14
                    self.match(twtlParser.T__2)
                    self.state = 15
                    localctx.duration = self.match(twtlParser.RATIONAL)


                self.state = 19
                self._errHandler.sync(self)
                _la = self._input.LA(1)
                if _la==19:
                    self.state = 18
                    localctx.negated = self.match(twtlParser.NOT)


                self.state = 21
                localctx.prop = self.nf(0)
                pass

            elif la_ == 3:
                self.state = 22
                localctx.op = self.match(twtlParser.NOT)
                self.state = 23
                localctx.child = self.formula(4)
                pass

            elif la_ == 4:
                self.state = 24
                localctx.op = self.match(twtlParser.T__3)
                self.state = 25
                localctx.child = self.formula(0)
                self.state = 26
                self.match(twtlParser.T__4)
                self.state = 27
                self.match(twtlParser.T__2)
                self.state = 28
                self.match(twtlParser.T__3)
                self.state = 29
                localctx.low = self.match(twtlParser.RATIONAL)
                self.state = 30
                self.match(twtlParser.T__5)
                self.state = 31
                localctx.high = self.match(twtlParser.RATIONAL)
                self.state = 32
                self.match(twtlParser.T__4)
                pass


            self._ctx.stop = self._input.LT(-1)
            self.state = 47
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,4,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    self.state = 45
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,3,self._ctx)
                    if la_ == 1:
                        localctx = twtlParser.FormulaContext(self, _parentctx, _parentState)
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_formula)
                        self.state = 36
                        if not self.precpred(self._ctx, 6):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 6)")
                        self.state = 37
                        localctx.op = self.match(twtlParser.CONCAT)
                        self.state = 38
                        localctx.right = self.formula(7)
                        pass

                    elif la_ == 2:
                        localctx = twtlParser.FormulaContext(self, _parentctx, _parentState)
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_formula)
                        self.state = 39
                        if not self.precpred(self._ctx, 2):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 2)")
                        self.state = 40
                        localctx.op = self.match(twtlParser.OR)
                        self.state = 41
                        localctx.right = self.formula(3)
                        pass

                    elif la_ == 3:
                        localctx = twtlParser.FormulaContext(self, _parentctx, _parentState)
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_formula)
                        self.state = 42
                        if not self.precpred(self._ctx, 1):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 1)")
                        self.state = 43
                        localctx.op = self.match(twtlParser.AND)
                        self.state = 44
                        localctx.right = self.formula(2)
                        pass

             
                self.state = 49
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,4,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class NfContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.left = None # NfContext
            self.op = None # Token
            self.right = None # NfContext

        def FALSE(self):
            return self.getToken(twtlParser.FALSE, 0)

        def TRUE(self):
            return self.getToken(twtlParser.TRUE, 0)

        def booleanExpr(self):
            return self.getTypedRuleContext(twtlParser.BooleanExprContext,0)


        def nf(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(twtlParser.NfContext)
            else:
                return self.getTypedRuleContext(twtlParser.NfContext,i)


        def OR(self):
            return self.getToken(twtlParser.OR, 0)

        def AND(self):
            return self.getToken(twtlParser.AND, 0)

        def getRuleIndex(self):
            return twtlParser.RULE_nf

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterNf" ):
                listener.enterNf(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitNf" ):
                listener.exitNf(self)



    def nf(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = twtlParser.NfContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 2
        self.enterRecursionRule(localctx, 2, self.RULE_nf, _p)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 54
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,5,self._ctx)
            if la_ == 1:
                self.state = 51
                localctx.op = self.match(twtlParser.FALSE)
                pass

            elif la_ == 2:
                self.state = 52
                localctx.op = self.match(twtlParser.TRUE)
                pass

            elif la_ == 3:
                self.state = 53
                self.booleanExpr()
                pass


            self._ctx.stop = self._input.LT(-1)
            self.state = 64
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,7,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    self.state = 62
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,6,self._ctx)
                    if la_ == 1:
                        localctx = twtlParser.NfContext(self, _parentctx, _parentState)
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_nf)
                        self.state = 56
                        if not self.precpred(self._ctx, 2):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 2)")
                        self.state = 57
                        localctx.op = self.match(twtlParser.OR)
                        self.state = 58
                        localctx.right = self.nf(3)
                        pass

                    elif la_ == 2:
                        localctx = twtlParser.NfContext(self, _parentctx, _parentState)
                        localctx.left = _prevctx
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_nf)
                        self.state = 59
                        if not self.precpred(self._ctx, 1):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 1)")
                        self.state = 60
                        localctx.op = self.match(twtlParser.AND)
                        self.state = 61
                        localctx.right = self.nf(2)
                        pass

             
                self.state = 66
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,7,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx


    class BooleanExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser
            self.op = None # Token
            self.left = None # ExprContext
            self.right = None # ExprContext

        def FALSE(self):
            return self.getToken(twtlParser.FALSE, 0)

        def TRUE(self):
            return self.getToken(twtlParser.TRUE, 0)

        def VARIABLE(self):
            return self.getToken(twtlParser.VARIABLE, 0)

        def expr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(twtlParser.ExprContext)
            else:
                return self.getTypedRuleContext(twtlParser.ExprContext,i)


        def getRuleIndex(self):
            return twtlParser.RULE_booleanExpr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterBooleanExpr" ):
                listener.enterBooleanExpr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitBooleanExpr" ):
                listener.exitBooleanExpr(self)




    def booleanExpr(self):

        localctx = twtlParser.BooleanExprContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_booleanExpr)
        self._la = 0 # Token type
        try:
            self.state = 74
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,8,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 67
                localctx.op = self.match(twtlParser.FALSE)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 68
                localctx.op = self.match(twtlParser.TRUE)
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 69
                localctx.op = self.match(twtlParser.VARIABLE)
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 70
                localctx.left = self.expr(0)
                self.state = 71
                localctx.op = self._input.LT(1)
                _la = self._input.LA(1)
                if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 3968) != 0)):
                    localctx.op = self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 72
                localctx.right = self.expr(0)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ExprContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def expr(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(twtlParser.ExprContext)
            else:
                return self.getTypedRuleContext(twtlParser.ExprContext,i)


        def VARIABLE(self):
            return self.getToken(twtlParser.VARIABLE, 0)

        def RATIONAL(self):
            return self.getToken(twtlParser.RATIONAL, 0)

        def getRuleIndex(self):
            return twtlParser.RULE_expr

        def enterRule(self, listener:ParseTreeListener):
            if hasattr( listener, "enterExpr" ):
                listener.enterExpr(self)

        def exitRule(self, listener:ParseTreeListener):
            if hasattr( listener, "exitExpr" ):
                listener.exitExpr(self)



    def expr(self, _p:int=0):
        _parentctx = self._ctx
        _parentState = self.state
        localctx = twtlParser.ExprContext(self, self._ctx, _parentState)
        _prevctx = localctx
        _startState = 6
        self.enterRecursionRule(localctx, 6, self.RULE_expr, _p)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 88
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,9,self._ctx)
            if la_ == 1:
                self.state = 77
                _la = self._input.LA(1)
                if not(_la==1 or _la==12):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 78
                self.expr(0)
                self.state = 79
                self.match(twtlParser.T__1)
                pass

            elif la_ == 2:
                self.state = 81
                self.match(twtlParser.VARIABLE)
                self.state = 82
                self.match(twtlParser.T__0)
                self.state = 83
                self.expr(0)
                self.state = 84
                self.match(twtlParser.T__1)
                pass

            elif la_ == 3:
                self.state = 86
                self.match(twtlParser.RATIONAL)
                pass

            elif la_ == 4:
                self.state = 87
                self.match(twtlParser.VARIABLE)
                pass


            self._ctx.stop = self._input.LT(-1)
            self.state = 101
            self._errHandler.sync(self)
            _alt = self._interp.adaptivePredict(self._input,11,self._ctx)
            while _alt!=2 and _alt!=ATN.INVALID_ALT_NUMBER:
                if _alt==1:
                    if self._parseListeners is not None:
                        self.triggerExitRuleEvent()
                    _prevctx = localctx
                    self.state = 99
                    self._errHandler.sync(self)
                    la_ = self._interp.adaptivePredict(self._input,10,self._ctx)
                    if la_ == 1:
                        localctx = twtlParser.ExprContext(self, _parentctx, _parentState)
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 90
                        if not self.precpred(self._ctx, 6):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 6)")
                        self.state = 91
                        self.match(twtlParser.T__2)
                        self.state = 92
                        self.expr(6)
                        pass

                    elif la_ == 2:
                        localctx = twtlParser.ExprContext(self, _parentctx, _parentState)
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 93
                        if not self.precpred(self._ctx, 4):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 4)")
                        self.state = 94
                        _la = self._input.LA(1)
                        if not(_la==13 or _la==14):
                            self._errHandler.recoverInline(self)
                        else:
                            self._errHandler.reportMatch(self)
                            self.consume()
                        self.state = 95
                        self.expr(5)
                        pass

                    elif la_ == 3:
                        localctx = twtlParser.ExprContext(self, _parentctx, _parentState)
                        self.pushNewRecursionContext(localctx, _startState, self.RULE_expr)
                        self.state = 96
                        if not self.precpred(self._ctx, 3):
                            from antlr4.error.Errors import FailedPredicateException
                            raise FailedPredicateException(self, "self.precpred(self._ctx, 3)")
                        self.state = 97
                        _la = self._input.LA(1)
                        if not(_la==15 or _la==16):
                            self._errHandler.recoverInline(self)
                        else:
                            self._errHandler.reportMatch(self)
                            self.consume()
                        self.state = 98
                        self.expr(4)
                        pass

             
                self.state = 103
                self._errHandler.sync(self)
                _alt = self._interp.adaptivePredict(self._input,11,self._ctx)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.unrollRecursionContexts(_parentctx)
        return localctx



    def sempred(self, localctx:RuleContext, ruleIndex:int, predIndex:int):
        if self._predicates == None:
            self._predicates = dict()
        self._predicates[0] = self.formula_sempred
        self._predicates[1] = self.nf_sempred
        self._predicates[3] = self.expr_sempred
        pred = self._predicates.get(ruleIndex, None)
        if pred is None:
            raise Exception("No predicate with index:" + str(ruleIndex))
        else:
            return pred(localctx, predIndex)

    def formula_sempred(self, localctx:FormulaContext, predIndex:int):
            if predIndex == 0:
                return self.precpred(self._ctx, 6)
         

            if predIndex == 1:
                return self.precpred(self._ctx, 2)
         

            if predIndex == 2:
                return self.precpred(self._ctx, 1)
         

    def nf_sempred(self, localctx:NfContext, predIndex:int):
            if predIndex == 3:
                return self.precpred(self._ctx, 2)
         

            if predIndex == 4:
                return self.precpred(self._ctx, 1)
         

    def expr_sempred(self, localctx:ExprContext, predIndex:int):
            if predIndex == 5:
                return self.precpred(self._ctx, 6)
         

            if predIndex == 6:
                return self.precpred(self._ctx, 4)
         

            if predIndex == 7:
                return self.precpred(self._ctx, 3)
         




