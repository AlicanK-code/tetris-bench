def score(board, placement):
    lines = placement["lines_cleared"]
    
    # Calculate holes correctly by checking each empty cell for filled cells above
    holes = 0
    for c in range(10):
        filled_above = False
        for r in range(20):
            if board[r][c]:
                filled_above = True
            else:
                if filled_above:
                    holes += 1
    
    # Calculate max_height (tallest column)
    max_height = 0
    for c in range(10):
        height = 0
        for r in reversed(range(20)):
            if board[r][c]:
                height += 1
            else:
                break
        max_height = max(max_height, height)
    
    # Calculate column heights for surface_unevenness (variance)
    column_heights = []
    for c in range(10):
        height = 0
        for r in reversed(range(20)):
            if board[r][c]:
                height += 1
            else:
                break
        column_heights.append(height)
    
    # Compute surface_unevenness as variance
    mean_height = sum(column_heights) / len(column_heights)
    variance = sum((h - mean_height)**2 for h in column_heights) / len(column_heights)
    surface_unevenness = variance
    
    # Return a weighted score to prioritize line clears, minimize holes, and reduce height/unevenness
    return lines * 1000 - holes * 100 - max_height * 50 - surface_unevenness * 20
