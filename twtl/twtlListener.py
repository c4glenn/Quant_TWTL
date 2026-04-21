# Generated from twtl.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .twtlParser import twtlParser
else:
    from twtlParser import twtlParser

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


# This class defines a complete listener for a parse tree produced by twtlParser.
class twtlListener(ParseTreeListener):

    # Enter a parse tree produced by twtlParser#formula.
    def enterFormula(self, ctx:twtlParser.FormulaContext):
        pass

    # Exit a parse tree produced by twtlParser#formula.
    def exitFormula(self, ctx:twtlParser.FormulaContext):
        pass


    # Enter a parse tree produced by twtlParser#nf.
    def enterNf(self, ctx:twtlParser.NfContext):
        pass

    # Exit a parse tree produced by twtlParser#nf.
    def exitNf(self, ctx:twtlParser.NfContext):
        pass


    # Enter a parse tree produced by twtlParser#booleanExpr.
    def enterBooleanExpr(self, ctx:twtlParser.BooleanExprContext):
        pass

    # Exit a parse tree produced by twtlParser#booleanExpr.
    def exitBooleanExpr(self, ctx:twtlParser.BooleanExprContext):
        pass


    # Enter a parse tree produced by twtlParser#expr.
    def enterExpr(self, ctx:twtlParser.ExprContext):
        pass

    # Exit a parse tree produced by twtlParser#expr.
    def exitExpr(self, ctx:twtlParser.ExprContext):
        pass



del twtlParser