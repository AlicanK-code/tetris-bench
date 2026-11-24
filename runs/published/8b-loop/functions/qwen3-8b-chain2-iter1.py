def score(board, placement):
    lines = placement["lines_cleared"]
    
    # Calculate holes
    holes = 0
    for c in range(10):
        filled = False
        for r in reversed(range(20)):
            if board[r][c]:
                filled = True
            else:
                if filled:
                    holes += 1
    
    # Calculate max_height (number of filled cells from bottom up)
    max_height = 0
    for c in range(10):
        height = 0
        for r in reversed(range(20)):
            if board[r][c]:
                height += 1
            else:
                break
        max_height = max(max_height, height)
    
    # Calculate empty_bottom_rows
    empty_bottom_rows = 0
    for r in reversed(range(20)):
        if all(not cell for cell in board[r]):
            empty_bottom_rows += 1
        else:
            break
    
    # Calculate surface_unevenness (standard deviation of column heights)
    column_heights = []
    for c in range(10):
        height = 0
        for r in reversed(range(20)):
            if board[r][c]:
                height += 1
            else:
                break
        column_heights.append(height)
    mean_height = sum(column_heights) / len(column_heights)
    variance = sum((h - mean_height)**2 for h in column_heights) / len(column_heights)
    surface_unevenness = math.sqrt(variance)
    
    # Return score with adjusted weights
    return (lines * 100 - holes * 100 - max_height * 50 - empty_bottom_rows * 50 
            - surface_unevenness * 20)
