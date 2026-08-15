def build_index(rows):
    seen = []
    for r in rows:
        if r not in seen:
            seen.append(r)
    return seen
