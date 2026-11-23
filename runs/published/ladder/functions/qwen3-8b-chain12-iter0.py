def score(board, placement):
    # Calculate holes
    holes = 0
    for c in range(10):
        filled_rows = [r for r in range(20) if board[r][c]]
        if filled_rows:
            min_filled_row = min(filled_rows)
        else:
            min_filled_row = None
        for r in range(20):
            if not board[r][c]:
                if (min_filled_row is None) or (min_filled_row > r):
                    holes += 1
    # Calculate max_height
    max_height = 0
    for c in range(10):
        current_max = 0
        for r in range(20):
            if board[r][c]:
                current_max = r
        max_height = max(max_height, current_max)
    # lines_cleared from placement
    lines_cleared = placement["lines_cleared"]
    # Compute score
    score_val = lines_cleared * 100 - holes * 1 - max_height * 0.5
    return float(score_val)
