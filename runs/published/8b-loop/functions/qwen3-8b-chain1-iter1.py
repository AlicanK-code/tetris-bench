def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    holes = 0
    for r in range(20):
        for c in range(10):
            if not board[r][c]:
                has_filled_above = any(board[row][c] for row in range(r))
                if has_filled_above:
                    holes += 1
    max_h = 0
    for c in range(10):
        count = sum(1 for r in range(20) if board[r][c])
        max_h = max(max_h, count)
    column_heights = [sum(1 for r in range(20) if board[r][c]) for c in range(10)]
    avg_h = sum(column_heights) / 10
    import math
    std_dev = math.sqrt(sum((h - avg_h)**2 for h in column_heights) / 10)
    score_val = lines_cleared * 100 - holes * 15 - max_h * 15 - std_dev * 10
    return float(score_val)
