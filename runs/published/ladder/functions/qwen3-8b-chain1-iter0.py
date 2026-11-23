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
    filled_cells = sum(1 for row in board for cell in row if cell)
    score_val = lines_cleared * 100 - holes * 5 - max_h * 5 - filled_cells * 1
    return float(score_val)
