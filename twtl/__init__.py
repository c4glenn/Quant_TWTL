'''
TWTL — Time Window Temporal Logic

Public API, structured to match PyTeLo module conventions.
'''

from .twtlLexer import twtlLexer
from .twtlParser import twtlParser

from .twtl_ast import (
    TWTLAbstractSyntaxTreeExtractor,
    Operation,
    RelOperation,
    TWTLFormula,
    to_ast,
)

from .twtl import (
    Trace,
    TraceBatch,
    norm,
    translate,
    robustness,
    agm_robustness,
    monitor_agm,
    monitor_agm_rt,
    incremental_monitor_agm,
    monitor_robustness,
    predicate_normalized_value,
    update_geometric_rosi,
    update_arithmetic_rosi,
    powermean,
    conjunction_function,
    disjunction_function,
)

__all__ = [
    # AST
    'TWTLAbstractSyntaxTreeExtractor',
    'Operation',
    'RelOperation',
    'TWTLFormula',
    'to_ast',
    # Trace
    'Trace',
    'TraceBatch',
    # DFA / translation
    'norm',
    'translate',
    # Robustness
    'robustness',
    'agm_robustness',
    # Monitoring
    'monitor_agm',
    'monitor_agm_rt',
    'incremental_monitor_agm',
    'monitor_robustness',
    # Helpers
    'predicate_normalized_value',
    'update_geometric_rosi',
    'update_arithmetic_rosi',
    'powermean',
    'conjunction_function',
    'disjunction_function',
]
