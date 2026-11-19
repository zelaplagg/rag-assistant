"""Keyword (BM25) scoring and rank fusion for hybrid retrieval. Standard library only."""
from __future__ import annotations

import math
import re
from collections import Counter

STOPWORDS = frozenset(
    "a an the is are was were be been of in on at to for from by with and or not "
    "what which who whom how why when where does do did can could should would i my me you your it its "
    "this that these those as about into than then there".split()
)
_TOKEN = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens without English stop words. Hyphenated words split ('top-k' -> top, k)."""
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class BM25:
    """Okapi BM25 over a fixed list of documents."""

    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(tokenize(d)) for d in docs]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = (sum(self.len) / len(docs)) if docs else 0.0
        df: Counter = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = tokenize(query)
        out = []
        for tf, dl in zip(self.tf, self.len):
            s = 0.0
            for t in q:
                f = tf.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1)))
            out.append(s)
        return out

    def rank(self, query: str) -> list[int]:
        """Indices of documents that match at least one query term, best first."""
        sc = self.scores(query)
        return [i for i in sorted(range(len(sc)), key=lambda i: -sc[i]) if sc[i] > 0]


def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal rank fusion: merge several best-first id lists into one."""
    score: dict[str, float] = {}
    for ranking in rankings:
        for pos, id_ in enumerate(ranking, 1):
            score[id_] = score.get(id_, 0.0) + 1.0 / (k + pos)
    return sorted(score, key=lambda i: (-score[i], i))
