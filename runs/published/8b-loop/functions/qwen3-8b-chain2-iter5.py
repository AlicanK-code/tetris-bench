def score(board, placement):
    lines = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for c in range(10):
        filled_above = False
        for r in range(20):
            if board[r][c]:
                filled_above = True
            else:
                if filled_above:
                    holes += 1
    
    # Calculate max_height and column_heights
    column_heights = []
    max_height = 0
    for c in range(10):
        height = 0
        for r in range(20):
            if board[r][c]:
                height += 1
            else:
                break
        column_heights.append(height)
        max_height = max(max_height, height)
    
    # Compute surface_unevenness as variance
    mean_height = sum(column_heights) / len(column_heights)
    variance = sum((h - mean_height)**2 for h in column_heights) / len(column_heights)
    surface_unevenness = variance
    
    # Return a weighted score
    return lines * 1000 - holes * 250 - max_height * 150 - surface_unevenness * 50
