def score(board, placement):
    holes = 0
    max_h = 0
    heights = []
    for c in range(10):
        filled_above = 0
        count = 0
        for r in range(20):
            if board[r][c]:
                filled_above += 1
                count += 1
            else:
                if filled_above > 0:
                    holes += 1
        max_h = max(max_h, count)
        heights.append(count)
    avg = sum(heights) / len(heights)
    unevenness = sum(abs(h - avg) for h in heights)
    lines_cleared = placement["lines_cleared"]
    score_val = lines_cleared * 1000 - holes * 10 - max_h * 5 - unevenness * 5
    return score_val
