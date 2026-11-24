def score(board, placement):
    # Calculate holes
    holes = 0
    for c in range(10):
        for r in range(20):
            if not board[r][c]:
                # Check if there's a filled cell below
                has_filled_below = False
                for dr in range(r + 1, 20):
                    if board[dr][c]:
                        has_filled_below = True
                        break
                if not has_filled_below:
                    holes += 1
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
    # Compute the score with adjusted weights
    lines_cleared = placement["lines_cleared"]
    score_value = (lines_cleared * 1000) - (holes * 50) - (max_height * 100) - (surface_unevenness * 20)
    return score_value
