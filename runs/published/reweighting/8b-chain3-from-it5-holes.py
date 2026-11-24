def score(board, placement):
    holes = 0
    heights = []
    max_h = 0
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
    return lines_cleared * 50 - holes * 1 - max_h * 150 - unevenness * 150
