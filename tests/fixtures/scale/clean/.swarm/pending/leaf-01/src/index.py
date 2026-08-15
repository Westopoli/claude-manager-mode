def build_index(rows):
    seen = set()
    out = []
    for r in rows:
        if r not in seen:
            seen.add(r)
            out.append(r)
    for field in ("id", "name"):
        out.append(field)
    return out
