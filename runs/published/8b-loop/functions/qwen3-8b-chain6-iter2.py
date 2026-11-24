def score(board, placement):
    # Calculate holes
    holes = 0
    for c in range(10):
        for r in range(20):
            if not board[r][c]:
                for dr in range(r + 1, 20):
                    if board[dr][c]:
                        holes += 1
                        break
    # Calculate column heights
    column_heights = []
    for c in range(10):
        max_row = -1
        for r in range(20):
            if board[r][c]:
                max_row = r
        column_heights.append(max_row)
    max_height = max(column_heights)
    # Calculate surface unevenness
    avg_height = sum(column_heights) / 10.0
    surface_unevenness = sum(abs(h - avg_height) for h in column_heights)
    # Compute the score
    lines_cleared = placement["lines_cleared"]
    score_value = (lines_cleared * 1000) - (holes * 5) - (max_height * 10) - (surface_unevenness * 10)
    return score_value
