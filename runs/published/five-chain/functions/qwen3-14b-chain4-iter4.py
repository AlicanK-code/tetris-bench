def score(board, placement):
    # Calculate number of holes
    holes = 0
    for col in range(10):
        filled_above = False
        for row in range(20):
            if board[row][col]:
                filled_above = True
            elif filled_above:
                holes += 1

    # Calculate column heights and surface roughness
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
    surface_roughness = sum(abs(heights[i] - heights[i + 1]) for i in range(9))

    # Combine all factors into a score
    lines_cleared = placement["lines_cleared"]
    score = (lines_cleared * 2000) - (holes * 150) - (max_height * 250) - (surface_roughness * 75)
    return float(score)
