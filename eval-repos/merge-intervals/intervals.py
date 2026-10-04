def merge_intervals(intervals):
    ordered = sorted([list(interval) for interval in intervals])
    merged = []

    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = end
        else:
            merged.append([start, end])

    return merged
