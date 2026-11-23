def score(board, placement):
    # Calculate holes
    holes = 0
    for col in range(10):
        has_filled_below = False
        for row in range(19, -1, -1):  # from bottom to top
            if board[row][col]:
                has_filled_below = True
            else:
                if has_filled_below:
                    holes += 1

    # Correctly calculate column heights
    column_heights = []
    for col in range(10):
        height = 0
        for row in range(19, -1, -1):  # check from bottom up
            if board[row][col]:
                height += 1
            else:
                break
        column_heights.append(height)
    surface_roughness = sum(abs(column_heights[i] - column_heights[i + 1]) for i in range(9))
    max_height = max(column_heights)

    # Combine factors into a score with adjusted weights
    lines_cleared = placement["lines_cleared"]
    return (lines_cleared * 1000) - (holes * 150) - (surface_roughness * 75) - (max_height * 100)
