def score(board, placement):
    # Calculate number of holes
    holes = 0
    for row in range(20):
        for col in range(10):
            if not board[row][col]:
                # Check if there's a filled cell below
                has_filled_below = False
                for r in range(row + 1, 20):
                    if board[r][col]:
                        has_filled_below = True
                        break
                if has_filled_below:
                    holes += 1

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
    score = (lines_cleared * 1000) - (holes * 20) - (max_height * 50) - (surface_roughness * 15)
    return float(score)
