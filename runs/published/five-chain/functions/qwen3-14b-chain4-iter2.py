def score(board, placement):
    # Calculate number of holes
    holes = 0
    for col in range(10):
        first_filled_row = None
        for row in range(19, -1, -1):
            if board[row][col]:
                first_filled_row = row
                break
        if first_filled_row is not None:
            holes += first_filled_row  # number of empty cells above the first filled cell

    # Calculate column heights for max height and surface roughness
    heights = []
    for col in range(10):
        h = 0
        for row in range(20):
            if board[row][col]:
                h += 1
            else:
                break
        heights.append(h)
    max_height = max(heights)
    surface_roughness = sum(abs(heights[i] - heights[i + 1]) for i in range(9))

    # Combine all factors into a score with adjusted weights
    lines_cleared = placement["lines_cleared"]
    filled_cells = sum(sum(row) for row in board)
    score = (lines_cleared * 1000) + (filled_cells * 10) - (holes * 50) - (max_height * 100) - (surface_roughness * 30)
    return float(score)
