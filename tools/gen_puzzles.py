"""Generate VectorWend puzzles -> puzzles.js (fixed order).

Run: python3 tools/gen_puzzles.py
Word source + definitions: ../vector-wordle/answers.js (copied as tools/answers.js).
Each puzzle: a themed word set packed into a grid; every open tile is used exactly
once, each word is a simple orthogonal path. Verified:
  1. intended solution is a valid partition of all open tiles (paths adjacent, no reuse)
  2. every puzzle word can be traced on exactly ONE tile set in the grid
  3. exact-cover uniqueness: using ANY of the 194 bank words, there is exactly one way
     to tile all open cells with words matching the slot lengths.
  4. the tile partition is also unique when ANY English word (ENABLE list, 4-8 letters) plus the bank
     may be used (a word and its reversal on the same tiles count as the same partition).
"""
import json, random, re, pathlib, itertools, sys, collections

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "answers.js"
OUT = HERE.parent / "puzzles.js"
N_PUZZLES = 156          # 1.5 years at 2 per week (Tue/Thu)
SEED = 20260928

rows = re.findall(r'\["([A-Z]+)","(\w+)","((?:[^"\\]|\\.)*)"\]', SRC.read_text())
BANK = {w: (c, d.replace('\\"', '"')) for w, c, d in rows}
assert len(BANK) >= 190, len(BANK)
BANNED = ["VALENT", "VECTOBAC", "VECTOLEX", "VECTOMAX", "SUMMIT", "MOSQUITODUNK", "ADAPCO", "CENTRAL", "ZOECON", "BAYER"]
assert not any(b in BANK for b in BANNED)

T = lambda s: s.split()
THEMES = {
 "Larval control": T("LARVA LARVAE PUPA PUPAE DIPPER INSTAR LARVAL SPINOSAD BACILLUS GRANULE BRIQUET TEMEPHOS SPINOSYN "
                     "WRIGGLER TUMBLER OVICIDE TOXIN SPORE DRAIN TREAT JUVENILE HORMONE GAMBUSIA COPEPOD FISH PREDATOR "
                     "NATULAR ALTOSID AQUABAC CENSOR COCOBEAR DUPLEX FOURSTAR DOSE LABEL"),
 "Spray night": T("SPRAY FOGGER SPRAYER TRUCK AERIAL DRONE DROPLET NOZZLE WIND BARRIER FOLIAGE ATOMIZER AEROSOL DILUENT "
                  "EMULSION MICRON SWATH NALED DOSE LABEL ROTATION RESIST EFFICACY DUSK ANVIL AQUAHALT BIOMIST CIELO DUET FLIT MERUS ZENIVEX"),
 "Breeding sites": T("WETLAND MARSH SWAMP POND DITCH CULVERT PUDDLE BIRDBATH GUTTER TIRE BUCKET WATER SEWER SUMP POOL CISTERN "
                     "SAUCER RAIN RAINFALL FLOOD TIDE HABITAT BREEDING CATTAIL RICE DAIRY TULE HYACINTH DETRITUS SHADE"),
 "Disease & surveillance": T("OUTBREAK VIRUS DISEASE MALARIA FEVER ZIKA DENGUE VIREMIA ENZOOTIC ZOONOSIS ZOONOTIC SEROTYPE SEROLOGY "
                             "FILARIA USUTU MAYARO SINDBIS PATHOGEN PARASITE ENDEMIC EPIDEMIC SENTINEL CHICKEN BIRDS CORVID AVIAN "
                             "EQUINE ASSAY TITER HOST BLOOD VECTOR SURVEY SAMPLE TRAP OVITRAP OCTENOL INSPECT"),
 "Mosquito anatomy": T("WINGS ANTENNA THORAX ABDOMEN HALTERES SCUTUM SPIRACLE PALPS LABIUM STYLET MIDGUT CHITIN SIPHON PECTEN SALIVA"),
 "Life cycle": T("EGGS RAFT HATCH LARVA LARVAE INSTAR PUPA PUPAE EMERGE ECDYSIS DIAPAUSE OVIPOSIT GRAVID AUTOGENY BROOD SWARM "
                 "BITE BLOOD NECTAR FEMALE MALE WRIGGLER TUMBLER JUVENILE HORMONE"),
 "Know your mosquito": T("CULEX AEDES CULISETA MANSONIA AEGYPTI PIPIENS TARSALIS CULICINE MOSQUITO SKEETER GNAT MIDGE INSECT "
                         "PEST INVASIVE STERILE NUISANCE DIPTERA VECTOR FEMALE MALE WINGS BUZZ"),
 "Backyard & public": T("DEET BUZZ ITCH WELT REPEL SCREEN NETTING SUMMER HUMID SEASON BIRDBATH GUTTER TIRE BUCKET SAUCER DISTRICT "
                        "COUNTY DRAIN DUSK DAWN BITE PEST NUISANCE WATER POOL RAIN SHADE"),
 "Clarke products": T("NATULAR ALTOSID AQUABAC CENSOR COCOBEAR DUPLEX FOURSTAR ANVIL AQUAHALT BIOMIST CIELO DUET FLIT MERUS ZENIVEX"),
}
for k in THEMES:
    THEMES[k] = [w for w in dict.fromkeys(THEMES[k]) if w in BANK]
missing = set(BANK) - set(itertools.chain(*THEMES.values()))
if missing: print("bank words not in any theme:", sorted(missing))

THEME_CYCLE = ["Larval control", "Breeding sites", "Disease & surveillance", "Clarke products", "Mosquito anatomy",
               "Spray night", "Life cycle", "Know your mosquito", "Backyard & public"]
# Odd puzzles fall on Tuesday (5x5), even puzzles on Thursday (6x6)
SIZES = [(5, 5), (6, 6)]
SPEC = {(5, 5): dict(k=(3, 5), walls=(0, 3)), (5, 6): dict(k=(4, 5), walls=(0, 3)), (6, 6): dict(k=(5, 6), walls=(0, 4))}

def nbrs(i, R, C):
    r, c = divmod(i, C)
    if r > 0: yield i - C
    if r < R - 1: yield i + C
    if c > 0: yield i - 1
    if c < C - 1: yield i + 1

def components(free, R, C):
    free = set(free); comps = []
    while free:
        s = free.pop(); st = [s]; comp = [s]
        while st:
            x = st.pop()
            for y in nbrs(x, R, C):
                if y in free: free.remove(y); st.append(y); comp.append(y)
        comps.append(comp)
    return comps

def can_split(sizes, lengths):
    """can multiset lengths be partitioned into groups summing to each component size?"""
    sizes = sorted(sizes, reverse=True); lengths = sorted(lengths, reverse=True)
    if sum(sizes) != sum(lengths): return False
    bins = list(sizes)
    def rec(i):
        if i == len(lengths): return all(b == 0 for b in bins)
        seen = set()
        for j in range(len(bins)):
            if bins[j] >= lengths[i] and bins[j] not in seen:
                seen.add(bins[j]); bins[j] -= lengths[i]
                if rec(i + 1): return True
                bins[j] += lengths[i]
        return False
    return rec(0)

class Budget(Exception): pass

def partition(free, lengths, R, C, rng, budget):
    """Partition free cells into simple paths with given lengths. Returns list of (length, path)."""
    if not lengths: return [] if not free else None
    budget[0] -= 1
    if budget[0] < 0: raise Budget()
    # most constrained cell
    fl = list(free); rng.shuffle(fl)
    start = min(fl, key=lambda x: sum(1 for y in nbrs(x, R, C) if y in free))
    ls = list(set(lengths)); rng.shuffle(ls)
    for L in ls:
        paths = []
        def walk(path, used):
            if len(paths) >= 6: return
            if len(path) == L: paths.append(list(path)); return
            cand = [y for y in nbrs(path[-1], R, C) if y in free and y not in used]
            rng.shuffle(cand)
            cand.sort(key=lambda y: sum(1 for z in nbrs(y, R, C) if z in free and z not in used))
            for y in cand:
                path.append(y); used.add(y); walk(path, used); path.pop(); used.discard(y)
                if len(paths) >= 6: return
        walk([start], {start})
        rest_l = list(lengths); rest_l.remove(L)
        for p in paths:
            nf = free - set(p)
            if not can_split([len(c) for c in components(nf, R, C)], rest_l): continue
            sub = partition(nf, rest_l, R, C, rng, budget)
            if sub is not None: return [(L, p)] + sub
    return None

# ---------- verification ----------
def build_trie(words):
    trie = {}
    for w in words:
        t = trie
        for ch in w: t = t.setdefault(ch, {})
        t["$"] = w
    return trie
TRIE = build_trie(BANK)
# Stricter cover check: the bank words PLUS every 4-8 letter English word (ENABLE list, tools/words.js).
DICT = set(re.findall(r"[A-Z]{4,8}", (HERE / "words.js").read_text().upper())) | set(BANK)
DICT_TRIE = build_trie(DICT)

def occurrences(grid, R, C, trie=TRIE):
    """all (word, frozenset(cells), path) traceable in grid for bank words."""
    out = {}
    def dfs(i, t, path):
        ch = grid[i]
        if ch not in t: return
        t = t[ch]; path.append(i)
        if "$" in t: out.setdefault((t["$"], frozenset(path)), list(path))
        for j in nbrs(i, R, C):
            if j not in path and grid[j] != "#": dfs(j, t, path)
        path.pop()
    for i in range(R * C):
        if grid[i] != "#": dfs(i, trie, [])
    return out

def count_covers(grid, R, C, lengths, occ, limit=2):
    cells = [i for i in range(R * C) if grid[i] != "#"]
    need = collections.Counter(lengths)
    by_cell = collections.defaultdict(list)
    items = [(w, s) for (w, s) in occ if len(w) in need]
    for w, s in items:
        for c in s: by_cell[c].append((w, s))
    sols = []
    def rec(covered, need, chosen):
        if len(sols) >= limit: return
        unc = [c for c in cells if c not in covered]
        if not unc: sols.append(list(chosen)); return
        best = None
        for c in unc:
            opts = [(w, s) for (w, s) in by_cell[c] if need[len(w)] > 0 and not (s & covered)]
            if best is None or len(opts) < len(best[1]): best = (c, opts)
            if not opts: return
        for w, s in best[1]:
            need[len(w)] -= 1; chosen.append(w)
            rec(covered | s, need, chosen)
            need[len(w)] += 1; chosen.pop()
    rec(frozenset(), need, [])
    return sols

def verify(p):
    R, C, grid = p["rows"], p["cols"], p["grid"]
    used = []
    for wd in p["words"]:
        w, path = wd["w"], wd["path"]
        assert "".join(grid[i] for i in path) == w, (w, path)
        assert len(set(path)) == len(path)
        for a, b in zip(path, path[1:]): assert b in set(nbrs(a, R, C)), (w, a, b)
        used += path
    open_cells = [i for i in range(R * C) if grid[i] != "#"]
    assert sorted(used) == open_cells, "tiles not covered exactly once"
    occ = occurrences(grid, R, C)
    for wd in p["words"]:
        sets = {s for (w, s) in occ if w == wd["w"]}
        if sets != {frozenset(wd["path"])}: return "word %s traceable in %d places" % (wd["w"], len(sets))
    lens = [len(wd["w"]) for wd in p["words"]]
    sols = count_covers(grid, R, C, lens, occ)
    if len(sols) != 1: return "%d exact covers" % len(sols)
    # For the dictionary pass only the tile partition matters (e.g. TIDE read backwards is EDIT on the
    # very same tiles, which isn't a different solution), so collapse occurrences to distinct tile sets.
    docc = {("?" * len(s), s): 1 for (w, s) in occurrences(grid, R, C, DICT_TRIE)}
    sols = count_covers(grid, R, C, lens, docc)
    if len(sols) != 1: return "%d tile partitions with English dictionary" % len(sols)
    return None

# ---------- generation ----------
def make_puzzle(theme, R, C, rng, last_used, idx, recent_sets):
    pool = THEMES[theme]; spec = SPEC[(R, C)]; N = R * C
    for attempt in range(8000):
        k = rng.randint(*spec["k"])
        # weight words by staleness
        def wt(w): return 1 + min(40, idx - last_used.get(w, -99)) ** 1.5
        cand = list(pool); chosen = []
        fresh = [w for w in pool if w not in last_used]
        if fresh and attempt < 3000:  # make sure every bank word gets used at least once
            w = rng.choice(fresh); chosen.append(w); cand.remove(w)
        for _ in range(k - len(chosen)):
            ws = [wt(w) for w in cand]
            w = rng.choices(cand, ws)[0]; chosen.append(w); cand.remove(w)
        S = sum(map(len, chosen)); walls = N - S
        if not (spec["walls"][0] <= walls <= spec["walls"][1]): continue
        if frozenset(chosen) in recent_sets: continue
        # distinct lengths aren't required, but avoid two identical words obviously
        for _ in range(6):
            cells = list(range(N)); rng.shuffle(cells)
            wall_set = set(cells[:walls])
            free = set(range(N)) - wall_set
            comps = components(free, R, C)
            if not can_split([len(c) for c in comps], [len(w) for w in chosen]): continue
            try:
                parts = partition(free, [len(w) for w in chosen], R, C, rng, [400])
            except Budget:
                continue
            if not parts: continue
            words_left = list(chosen); rng.shuffle(words_left)
            grid = ["#"] * N; placed = []
            for L, path in parts:
                w = next(x for x in words_left if len(x) == L); words_left.remove(w)
                if rng.random() < 0.5: path = path[::-1]
                for ch, i in zip(w, path): grid[i] = ch
                placed.append({"w": w, "path": path})
            placed.sort(key=lambda d: (-len(d["w"]), d["w"]))
            p = {"theme": theme, "rows": R, "cols": C, "grid": "".join(grid), "words": placed}
            err = verify(p)
            if err is None: return p, attempt
    raise RuntimeError("failed %s %sx%s" % (theme, R, C))

def main():
    rng = random.Random(SEED)
    puzzles = []; last_used = {}; recent = []
    for n in range(N_PUZZLES):
        theme = THEME_CYCLE[n % len(THEME_CYCLE)]
        R, C = SIZES[n % 2]
        p, att = make_puzzle(theme, R, C, rng, last_used, n, set(recent[-60:]))
        for wd in p["words"]: last_used[wd["w"]] = n
        recent.append(frozenset(wd["w"] for wd in p["words"]))
        puzzles.append(p)
        print("#%d %dx%d %-24s walls=%d %s (attempts %d)" % (n + 1, R, C, theme, p["grid"].count("#"), [w["w"] for w in p["words"]], att))
    # final re-verification
    for p in puzzles: assert verify(p) is None
    used = sorted({wd["w"] for p in puzzles for wd in p["words"]})
    words = {w: [BANK[w][0], BANK[w][1]] for w in used}
    js = ("/* VectorWend puzzles: generated by tools/gen_puzzles.py (seed %d). Fixed order: puzzle #n = WEND_PUZZLES[(n-1) %% length].\n"
          " * grid: row-major letters, '#' = wall. path: tile indices in reading order. Regenerating changes future puzzles. */\n" % SEED)
    js += "window.WEND_WORDS = " + json.dumps(words, ensure_ascii=False, separators=(",", ":")) + ";\n"
    js += "window.WEND_PUZZLES = [\n" + ",\n".join(json.dumps(p, separators=(",", ":")) for p in puzzles) + "\n];\n"
    OUT.write_text(js)
    c = collections.Counter(wd["w"] for p in puzzles for wd in p["words"])
    print("\n%d puzzles, %d distinct words; max reuse %s; sizes %s; walls %s" % (len(puzzles), len(used), c.most_common(5),
          collections.Counter("%dx%d" % (p["rows"], p["cols"]) for p in puzzles), collections.Counter(p["grid"].count("#") for p in puzzles)))

if __name__ == "__main__":
    main()
