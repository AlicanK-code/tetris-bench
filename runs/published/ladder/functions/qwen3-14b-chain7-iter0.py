def score(board, placement):
    # Calculate column heights
    columns_heights = []
    for col in range(10):
        height = 0
        for row in range(20):
            if board[row][col]:
                height += 1
            else:
                break
        columns_heights.append(height)
    max_height = max(columns_heights)
    
    # Calculate holes
    holes = 0
    for col in range(10):
        previous_filled = False
        for row in range(20):
            if board[row][col]:
                previous_filled = True
            else:
                if previous_filled:
                    holes += 1
    
    # Calculate roughness
    roughness = 0
    for i in range(9):
        roughness += abs(columns_heights[i] - columns_heights[i+1])
    
    # Compute the score
    lines_cleared = placement["lines_cleared"]
    score_value = (lines_cleared * 10) - (max_height * 0.5) - (holes * 0.3) - (roughness * 0.2)
    
    # Add a small term based on placement parameters to ensure uniqueness
    unique_term = placement["column"] + placement["row"] + placement["rotation"] + ord(placement["kind"])
    score_value += unique_term * 0.0001
    
    return score_value
