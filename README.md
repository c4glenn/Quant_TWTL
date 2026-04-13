# TWTL — Time Window Temporal Logic

A Python library for parsing, monitoring, and synthesizing controllers for
**Time Window Temporal Logic (TWTL)** specifications.

TWTL is a fragment of temporal logic that combines hard deadlines with boolean
and temporal structure, making it well-suited for robotic mission planning and
runtime monitoring.  This library is structured to integrate cleanly with
[PyTeLo](https://github.com/erl-lehigh/PyTeLo).

## Features

- **Parser** — ANTLR-4 grammar (`twtl.g4`) with generated lexer/parser/visitor
- **AST** — `TWTLFormula` node class with `bounds()`, `variables()`, and `to_ast()`
- **Robustness** — classical (`robustness`) and AGM power-mean (`agm_robustness`) semantics
- **Monitoring** — offline (`monitor_agm`), partial-signal (`monitor_agm`), and
  incremental singleton-observation (`incremental_monitor_agm`) monitors
- **DFA translation** — `translate()` converts a TWTL AST to a normal or infinity DFA
- **Synthesis** — automata-based control policy synthesis from TWTL formulae

## Installation

### Dependencies

```bash
pip install antlr4-python3-runtime==4.7.1
pip install numpy scipy ordered-set
```

ANTLR 4 is also required to regenerate the lexer/parser if you modify `twtl.g4`:

```bash
antlr4 -Dlanguage=Python3 twtl/twtl.g4
```

### Install from source

```bash
git clone https://github.com/<your-username>/twtl.git
cd twtl
pip install -e .
```

## Quick start

```python
from twtl import to_ast, Trace, robustness, agm_robustness
import numpy as np

# 1. Parse a formula
formula = 'H^3 s>1 . [H^2 s<5]^[0,8]'
ast = to_ast(formula)

print(ast.bounds())      # [4, 12]
print(ast.variables())   # {'s'}

# 2. Build a trace
times  = np.linspace(0, 12, 13)
values = np.array([1.5] * 4 + [3.0] * 9)
bounds = {'s': (0, 8)}
trace  = Trace(['s'], times, [values], bounds)

# 3. Evaluate robustness
rho = robustness(ast, trace, times, dt=1.0)
print('rho:', rho)

# 4. Evaluate AGM robustness
eta = agm_robustness(ast, times, trace=trace, dt=1.0)
print('eta:', eta)
```

## Module structure

```
twtl/
├── twtl.g4             ANTLR grammar for TWTL
├── twtlLexer.py        ANTLR generated — do not edit
├── twtlParser.py       ANTLR generated — do not edit
├── twtlListener.py     ANTLR generated — do not edit
├── twtlVisitor.py      ANTLR generated — do not edit
├── twtl_ast.py         Operation, RelOperation, TWTLFormula, to_ast()
├── twtl.py             Robustness, monitoring, DFA translation, Trace classes
├── dfa.py              DFA data structures and operations
├── synthesis.py        Automata-based control policy synthesis
└── prop.py             Atomic proposition helper (AP class)
```

## Citation

If you use this library in your research, please cite:

```bibtex
@INPROCEEDINGS{ahmad_quantTWTL,
  author={Ahmad, Ahmad and Vasile, Cristian-Ioan and Tron, Roberto and Belta, Calin},
  booktitle={2023 62nd IEEE Conference on Decision and Control (CDC)}, 
  title={Robustness Measures and Monitors for Time Window Temporal Logic}, 
  year={2023},
  pages={6841-6846},
  doi={10.1109/CDC49753.2023.10383712}}
```

## License

MIT — see [LICENSE](LICENSE).
