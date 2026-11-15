#!/usr/bin/env python3
r"""Unit-aware calculator for napkin math. Standard library only.

    calc.py "1 TiB / 5 GiB/s"                          # -> 3.41 min
    calc.py "100k/s * 1 KiB * 30 day"                  # -> 241 TiB
    calc.py '260 TB * $0.02/GB/month to $/month'       # -> $5,200 /month
    calc.py "rps = 100k/s" "line = 1 KiB" "rps * line to TB/day"   # -> 8.85 TB/day

Rules
  * A number followed by a unit is a quantity: 5 GiB, 250 us, 3 GiB/s, $0.02/GB/month.
    A compound unit has no spaces around its "/": GiB/s, $/GB/month, req/s.
  * Operators with spaces around them are arithmetic: "1 TiB / 5 GiB/s" divides 1 TiB
    by the rate 5 GiB/s. Parentheses work as usual.
  * "<expr> to <unit>" shows the result in that unit (the dimensions must match).
    Without "to", the result is shown in the most readable unit.
  * "name = <expr>" defines a variable. Separate statements with ";", newlines or
    separate arguments; each statement's result is printed.
  * Number suffixes: 100k, 2.5M, 3bn (also 1e6). Percent: 5%.
  * Functions: log2 log10 ln sqrt ceil floor min max.

Units (case-sensitive)
  bytes    B KB MB GB TB PB EB (powers of 1000)   KiB MiB GiB TiB PiB EiB (powers of 1024)
  bits     bit Kbit Mbit Gbit Tbit, Kb Mb Gb Tb;  rates bps Kbps Mbps Gbps Tbps
  time     ns us μs ms s sec min h hr hour day week month (730 h, cloud billing) year (8760 h)
  money    $ USD
  counts   req op query row event msg call item user page key (plain counts, all 1)
  rates    rps qps IOPS (per second)

Exit status is 1 on a parse or dimension error, with the reason on stderr.
"""

import math
import re
import sys

# ---------------------------------------------------------------- quantities

DIMS = ("B", "s", "$")  # bytes, seconds, US dollars; counts are dimensionless


class CalcError(Exception):
    pass


class Q:
    """A value in base units (bytes, seconds, dollars) with integer dimension exponents."""

    __slots__ = ("v", "d")

    def __init__(self, v, d=(0, 0, 0)):
        self.v = float(v)
        self.d = tuple(d)

    def _same(self, o, op):
        if self.d != o.d:
            raise CalcError(f"can't {op} {dim_name(self.d)} and {dim_name(o.d)}")

    def __add__(self, o):
        self._same(o, "add")
        return Q(self.v + o.v, self.d)

    def __sub__(self, o):
        self._same(o, "subtract")
        return Q(self.v - o.v, self.d)

    def __mul__(self, o):
        return Q(self.v * o.v, tuple(a + b for a, b in zip(self.d, o.d)))

    def __truediv__(self, o):
        if o.v == 0:
            raise CalcError("division by zero")
        return Q(self.v / o.v, tuple(a - b for a, b in zip(self.d, o.d)))

    def __neg__(self):
        return Q(-self.v, self.d)

    def __pow__(self, o):
        if o.d != (0, 0, 0):
            raise CalcError("an exponent must be a plain number")
        n = o.v
        if self.d != (0, 0, 0) and n != int(n):
            raise CalcError("a quantity with units can only take an integer power")
        return Q(self.v**n, tuple(int(a * n) for a in self.d))

    @property
    def plain(self):
        return self.d == (0, 0, 0)


def dim_name(d):
    if d == (0, 0, 0):
        return "a plain number"
    num = [f"{u}^{e}" if e != 1 else u for u, e in zip(DIMS, d) if e > 0]
    den = [f"{u}^{-e}" if e != -1 else u for u, e in zip(DIMS, d) if e < 0]
    return ("*".join(num) or "1") + ("/" + "/".join(den) if den else "")


B, S, USD = (1, 0, 0), (0, 1, 0), (0, 0, 1)
UNITS = {}


def _unit(names, factor, dims):
    for n in names.split():
        UNITS[n] = Q(factor, dims)


_unit("B byte bytes", 1, B)
for i, p in enumerate("K M G T P E".split(), start=1):
    _unit(f"{p}B", 1000**i, B)
    _unit(f"{p}iB", 1024**i, B)
    _unit(f"{p}bit {p}b", 1000**i / 8, B)
    _unit(f"{p}bps", 1000**i / 8, (1, -1, 0))
_unit("kB", 1000, B)
_unit("kbit kb", 1000 / 8, B)
_unit("kbps", 1000 / 8, (1, -1, 0))
_unit("bit bits", 1 / 8, B)
_unit("bps", 1 / 8, (1, -1, 0))
_unit("ns", 1e-9, S)
_unit("us μs µs", 1e-6, S)
_unit("ms", 1e-3, S)
_unit("s sec secs second seconds", 1, S)
_unit("min mins minute minutes", 60, S)
_unit("h hr hrs hour hours", 3600, S)
_unit("day days", 86400, S)
_unit("week weeks", 7 * 86400, S)
_unit("month months mo", 730 * 3600, S)
_unit("year years yr", 8760 * 3600, S)
_unit("$ USD usd", 1, USD)
_unit(
    "req reqs request requests op ops query queries row rows event events msg msgs "
    "message messages call calls item items user users page pages key keys",
    1,
    (0, 0, 0),
)
_unit("rps qps RPS QPS IOPS iops", 1, (0, -1, 0))
_unit("%", 0.01, (0, 0, 0))

SUFFIXES = {"k": 1e3, "K": 1e3, "M": 1e6, "bn": 1e9, "G": 1e9}

FUNCS = {
    "log2": lambda q: _plain_fn(q, math.log2, "log2"),
    "log10": lambda q: _plain_fn(q, math.log10, "log10"),
    "ln": lambda q: _plain_fn(q, math.log, "ln"),
    "ceil": lambda q: Q(math.ceil(q.v), q.d),
    "floor": lambda q: Q(math.floor(q.v), q.d),
    "sqrt": lambda q: _sqrt(q),
}


def _plain_fn(q, f, name):
    if not q.plain:
        raise CalcError(f"{name}() needs a plain number, not {dim_name(q.d)}")
    if q.v <= 0:
        raise CalcError(f"{name}() of a non-positive number")
    return Q(f(q.v))


def _sqrt(q):
    if any(e % 2 for e in q.d):
        raise CalcError(f"sqrt() of {dim_name(q.d)} has no unit")
    return Q(math.sqrt(q.v), tuple(e // 2 for e in q.d))


# ---------------------------------------------------------------- tokenizer

TOKEN = re.compile(
    r"""
    (?P<sep>[;\n])
  | (?P<ws>[ \t\r]+)
  | (?P<num>(?:\d[\d_,]*(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:bn|[kKMG](?![A-Za-z]))?)
  | (?P<ident>[A-Za-zμµ_][A-Za-z0-9μµ_]*|\$|%)
  | (?P<op>\*\*|[-+*/^(),=])
    """,
    re.X,
)


class Tok:
    __slots__ = ("kind", "text", "space")

    def __init__(self, kind, text, space):
        self.kind, self.text, self.space = kind, text, space

    def __repr__(self):
        return f"{self.kind}:{self.text}"


def tokenize(src):
    toks, pos, space = [], 0, True
    while pos < len(src):
        m = TOKEN.match(src, pos)
        if not m:
            raise CalcError(f"unexpected {src[pos]!r} at column {pos + 1}")
        kind, text = m.lastgroup, m.group()
        pos = m.end()
        if kind == "ws":
            space = True
            continue
        if kind == "op" and text == "**":
            text = "^"
        toks.append(Tok(kind, text, space))
        space = kind == "sep"
    toks.append(Tok("end", "", True))
    return toks


def parse_number(text):
    mult = 1.0
    for suf, f in SUFFIXES.items():
        if text.endswith(suf) and not re.search(r"[eE]\d*$", text[: -len(suf)] + "0"):
            text, mult = text[: -len(suf)], f
            break
    text = text.replace("_", "").replace(",", "")
    try:
        return float(text) * mult
    except ValueError:
        raise CalcError(f"bad number {text!r}") from None


# ---------------------------------------------------------------- parser

class Parser:
    def __init__(self, toks, env):
        self.t, self.i, self.env = toks, 0, env

    @property
    def cur(self):
        return self.t[self.i]

    def peek(self, k=1):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def take(self, text=None):
        tok = self.cur
        if text is not None and tok.text != text:
            raise CalcError(f"expected {text!r}, got {tok.text or 'end of input'!r}")
        self.i += 1
        return tok

    def is_unit(self, tok):
        return tok.kind == "ident" and tok.text in UNITS and tok.text not in self.env

    # statement := [name '='] expr ['to' expr]
    def statement(self):
        name = None
        if self.cur.kind == "ident" and self.peek().text == "=":
            name = self.take().text
            # Count and rate units (rps, users, ...) may be reused as variable names;
            # byte, time and money units may not, or "5 GB" would stop meaning gigabytes.
            if name in FUNCS or name == "to" or (name in UNITS and UNITS[name].d not in ((0, 0, 0), (0, -1, 0))):
                raise CalcError(f"{name!r} is a unit or function name; pick another variable name")
            self.take("=")
        value = self.expr()
        target = None
        if self.cur.kind == "ident" and self.cur.text == "to":
            self.take()
            start = self.i
            target_q = self.expr()
            target = (target_q, " ".join(t.text for t in self.t[start:self.i]).replace(" / ", "/"))
        if self.cur.kind not in ("sep", "end"):
            raise CalcError(f"unexpected {self.cur.text!r}")
        return name, value, target

    def expr(self):
        q = self.term()
        while self.cur.text in ("+", "-") and self.cur.kind == "op":
            op = self.take().text
            r = self.term()
            q = q + r if op == "+" else q - r
        return q

    def term(self):
        q = self.unary()
        while self.cur.kind == "op" and self.cur.text in ("*", "/"):
            op = self.take().text
            r = self.unary()
            q = q * r if op == "*" else q / r
        return q

    def unary(self):
        if self.cur.kind == "op" and self.cur.text in ("-", "+"):
            neg = self.take().text == "-"
            q = self.unary()
            return -q if neg else q
        return self.power()

    def power(self):
        q = self.atom()
        if self.cur.kind == "op" and self.cur.text == "^":
            self.take()
            q = q ** self.unary()  # right-associative
        return q

    def atom(self):
        tok = self.cur
        if tok.kind == "num":
            self.take()
            q = Q(parse_number(tok.text))
            if self.is_unit(self.cur) and self.cur.text != "$":
                q = q * self.unit_chain()
            elif self.attached_per():
                q = q * self.per_chain()
            return q
        if tok.kind == "ident" and tok.text == "$":
            self.take()
            if self.cur.kind == "num":  # $0.02, $0.02/GB/month
                q = Q(parse_number(self.take().text), USD)
                if self.attached_per():
                    q = q * self.per_chain()
                return q
            q = UNITS["$"]
            if self.attached_per():
                q = q * self.per_chain()
            return q
        if tok.kind == "ident" and tok.text in FUNCS or tok.text in ("min", "max") and self.peek().text == "(":
            return self.call()
        if tok.kind == "ident":
            if tok.text in self.env:
                self.take()
                return self.env[tok.text]
            if tok.text in UNITS:
                return self.unit_chain()
            raise CalcError(f"unknown name {tok.text!r} (not a unit or a defined variable)")
        if tok.text == "(":
            self.take()
            q = self.expr()
            self.take(")")
            return q
        raise CalcError(f"unexpected {tok.text or 'end of input'!r}")

    def call(self):
        name = self.take().text
        self.take("(")
        args = [self.expr()]
        while self.cur.text == ",":
            self.take()
            args.append(self.expr())
        self.take(")")
        if name in ("min", "max"):
            for a in args[1:]:
                args[0]._same(a, "compare")
            return (min if name == "min" else max)(args, key=lambda q: q.v)
        if len(args) != 1:
            raise CalcError(f"{name}() takes one argument")
        return FUNCS[name](args[0])

    def attached_per(self):
        """A '/' glued to the previous token and to a unit after it: the /s in 100k/s."""
        nxt = self.peek()
        return (
            self.cur.kind == "op" and self.cur.text == "/" and not self.cur.space
            and self.is_unit(nxt) and not nxt.space
        )

    def unit_chain(self):
        """GiB, GiB/s, $/GB/month, s^2: a unit and any glued /unit or ^n parts."""
        q = UNITS[self.take().text]
        q = self.glued_power(q)
        return q * self.per_chain() if self.attached_per() else q

    def per_chain(self):
        q = Q(1)
        while self.attached_per():
            self.take("/")
            u = self.glued_power(UNITS[self.take().text])
            q = q / u
        return q

    def glued_power(self, q):
        if self.cur.text == "^" and not self.cur.space and self.peek().kind == "num":
            self.take()
            q = q ** Q(parse_number(self.take().text))
        return q


# ---------------------------------------------------------------- formatting

def fmt_num(v):
    """Three significant figures, thousands separators, exponent only when huge or tiny."""
    if v == 0:
        return "0"
    a = abs(v)
    if 1e-3 <= a < 1e9:
        places = 2 - int(math.floor(math.log10(a)))  # negative for >= 1000: 132710 -> 133000
        r = round(v, places)
        digits = max(0, places)
        s = f"{r:,.{digits}f}"
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    m, e = f"{v:.2e}".split("e")
    return f"{m.rstrip('0').rstrip('.')}e{int(e)}"


def napkin(v):
    """One significant digit: the number to remember."""
    if v == 0:
        return 0.0
    e = math.floor(math.log10(abs(v)))
    return round(v / 10**e) * 10**e


def pick(v, ladder):
    """The largest unit in the ladder (ascending) whose value is >= 1."""
    best = ladder[0]
    for name, factor in ladder:
        if abs(v) >= factor * 0.9995:
            best = (name, factor)
    return best


BIN = [("B", 1)] + [(f"{p}iB", 1024**i) for i, p in enumerate("KMGTPE", 1)]
DEC = [("B", 1)] + [(f"{p}B", 1000**i) for i, p in enumerate("KMGTPE", 1)]
BITS = [("bit/s", 1 / 8)] + [(f"{p}bit/s", 1000**i / 8) for i, p in enumerate("KMGT", 1)]
TIME = [("ns", 1e-9), ("μs", 1e-6), ("ms", 1e-3), ("s", 1), ("min", 60), ("h", 3600),
        ("days", 86400), ("years", 8760 * 3600)]


def in_unit(v, unit, factor):
    return f"{fmt_num(v / factor)} {unit}"


def describe(q):
    """(primary, [alternatives]) for a quantity, in readable units."""
    v, d = q.v, q.d
    if d == (0, 0, 0):
        words = [(1e12, "trillion"), (1e9, "billion"), (1e6, "million")]
        alt = [f"{fmt_num(v / f)} {w}" for f, w in words if abs(v) >= f][:1]
        return fmt_num(v), alt
    if d == B:
        u, f = pick(v, BIN)
        du, df = pick(v, DEC)
        return in_unit(v, u, f), [in_unit(v, du, df)] if du != "B" else []
    if d == S:
        u, f = pick(v, TIME)
        return in_unit(v, u, f), []
    if d == (1, -1, 0):
        u, f = pick(v, BIN)
        bu, bf = pick(v, BITS)
        return in_unit(v, u + "/s", f), [in_unit(v, bu, bf), in_unit(v * 86400, pick(v * 86400, DEC)[0] + "/day", pick(v * 86400, DEC)[1])]
    if d == (0, -1, 0):
        return f"{fmt_num(v)} /s", [f"{fmt_num(v * 86400)} /day", f"{fmt_num(v * 730 * 3600)} /month"]
    if d == USD:
        return f"${fmt_num(v)}", []
    if d == (0, -1, 1):
        return f"${fmt_num(v * 730 * 3600)} /month", [f"${fmt_num(v * 8760 * 3600)} /year", f"${fmt_num(v * 3600)} /hour"]
    if d == (-1, 0, 1):
        return f"${fmt_num(v * 1e9)} /GB", [f"${fmt_num(v * 1024**4)} /TiB"]
    if d == (-1, -1, 1):
        return f"${fmt_num(v * 1e9 * 730 * 3600)} /GB/month", []
    if d == (1, 1, 0):
        u, f = pick(v / 730 / 3600, DEC)
        return f"{fmt_num(v / 730 / 3600 / f)} {u}-months", []
    if d == (0, 1, -1):
        return f"{fmt_num(v)} s/$", []
    return f"{fmt_num(v)} {dim_name(d)}", []


def render(name, q, target):
    if target:
        tq, ttext = target
        if tq.d != q.d:
            raise CalcError(f"can't show {dim_name(q.d)} in {ttext} ({dim_name(tq.d)})")
        n = q.v / tq.v
        prefix = ttext.split("/")[0]
        unit = ttext
        if prefix == "$" and len(ttext) > 1:  # "$/month": show as $X /month
            primary = f"${fmt_num(n)} {ttext[1:]}"
            approx = f"${fmt_num(napkin(n))} {ttext[1:]}"
        elif ttext == "$":
            primary, approx = f"${fmt_num(n)}", f"${fmt_num(napkin(n))}"
        else:
            primary, approx = f"{fmt_num(n)} {unit}", f"{fmt_num(napkin(n))} {unit}"
        alts = []
    else:
        primary, alts = describe(q)
        approx = None
        m = re.match(r"^(\$?)(-?[\d,.]+(?:e-?\d+)?)(.*)$", primary)
        if m:
            approx = f"{m.group(1)}{fmt_num(napkin(float(m.group(2).replace(',', ''))))}{m.group(3)}"
    out = f"{name} = {primary}" if name else f"= {primary}"
    if alts:
        out += f"  ({', '.join(alts)})"
    if approx and approx != primary:
        out += f"  ≈ {approx}"
    return out


# ---------------------------------------------------------------- driver

def run(src, env=None):
    """Evaluate statements; return a list of (source line, rendered result)."""
    env = {} if env is None else env
    toks = tokenize(src)
    p = Parser(toks, env)
    results = []
    while p.cur.kind != "end":
        if p.cur.kind == "sep":
            p.take()
            continue
        start = p.i
        name, q, target = p.statement()
        text = " ".join(t.text for t in toks[start:p.i])
        if name:
            env[name] = q
        results.append((text, render(name, q, target), q))
    return results


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    src = sys.stdin.read() if argv == ["-"] else "\n".join(argv)
    try:
        for _, line, _ in run(src):
            print(line)
    except CalcError as e:
        print(f"calc: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
