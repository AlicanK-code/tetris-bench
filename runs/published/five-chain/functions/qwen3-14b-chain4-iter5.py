def score(board, placement):
    # Count holes: empty cells below filled ones
    holes = 0
    for col in range(10):
        filled_above = False
        for row in range(20):
            if board[row][col]:
                filled_above = True
            elif filled_above:
                holes += 1

    # Calculate column heights from bottom up (filled cells starting at the bottom)
    heights = []
    for col in range(10):
        h = 0
        for row in range(19, -1, -1):
            if board[row][col]:
                h += 1
            else:
                break
        heights.append(h)
    max_height = max(heights)
    total_height = sum(heights)
    surface_roughness = sum(abs(heights[i] - heights[i+1]) for i in range(9))

    # Weighted combination of factors
    lines_cleared = placement["lines_cleared"]
    score = (lines_cleared * 1000) - (holes * 40) - (total_height * 8) - (max_height * 35) - (surface_roughness * 15)
    return float(score)
