"""Find the policy passages that best match a customer question.

Steps:
1. Split each policy into short passages (2 sentences each).
2. Turn text into keywords (lowercase, drop common words, cut endings like -s, -ing).
3. Score every passage against the question with BM25, a classic search formula:
   words that are rare across the policies count more than common ones.
"""
import math
import re
from pathlib import Path

POLICY_DIR = Path(__file__).resolve().parent.parent / "policies"

STOPWORDS = set(
    "a an the and or but if of to in on at for from by with without about as is are was were be been "
    "being do does did can could would should will shall may might must i me my we our you your it its "
    "this that these those there here what which who whom how when where why not no yes any some all into "
    "than then so too very just get got have has had please hi hello after before ago since also".split()
)


def stem(word):
    word = re.sub(r"(ings|ing|ed|es|s)$", "", word)
    return re.sub(r"ies$", "y", word)


def keywords(text):
    words = re.findall(r"[a-z0-9$]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


def load_passages():
    passages = []
    for path in sorted(POLICY_DIR.glob("*.md")):
        lines = path.read_text().strip().splitlines()
        title = lines[0].lstrip("# ").strip()
        body = " ".join(line for line in lines[1:] if line.strip())
        sentences = re.findall(r"[^.]+\.", body) or [body]
        for i in range(0, len(sentences), 2):
            text = " ".join(s.strip() for s in sentences[i:i + 2])
            passages.append({
                "policy": path.stem,
                "title": title,
                "text": text,
                "words": keywords(title + " " + text),
            })
    return passages


class Retriever:
    def __init__(self, passages=None, k1=1.4, b=0.75):
        self.passages = passages or load_passages()
        self.k1, self.b = k1, b
        self.avg_len = sum(len(p["words"]) for p in self.passages) / len(self.passages)
        self.doc_freq = {}
        for p in self.passages:
            for w in set(p["words"]):
                self.doc_freq[w] = self.doc_freq.get(w, 0) + 1

    def bm25(self, query_words, passage):
        n = len(self.passages)
        score = 0.0
        for w in set(query_words):
            freq = passage["words"].count(w)
            if not freq:
                continue
            df = self.doc_freq.get(w, 0)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            norm = freq + self.k1 * (1 - self.b + self.b * len(passage["words"]) / self.avg_len)
            score += idf * freq * (self.k1 + 1) / norm
        return score

    def search(self, question, top_k=3):
        query_words = keywords(question)
        scored = [dict(p, score=self.bm25(query_words, p)) for p in self.passages]
        scored.sort(key=lambda p: p["score"], reverse=True)
        return scored[:top_k]
