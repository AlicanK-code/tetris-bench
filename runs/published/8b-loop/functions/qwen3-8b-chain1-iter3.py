def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    holes = 0
    for r in range(20):
        for c in range(10):
            if not board[r][c]:
                has_filled_above = any(board[row][c] for row in range(r))
                if has_filled_above:
                    holes += 1
    column_heights = [sum(1 for r in range(20) if board[r][c]) for c in range(10)]
    max_h = max(column_heights)
    avg_h = sum(column_heights) / 10
    std_dev = (sum((h - avg_h)**2 for h in column_heights) / 10)**0.5
    score_val = lines_cleared * 100 - holes * 30 - max_h * 5 - std_dev * 5
    return float(score_val)
