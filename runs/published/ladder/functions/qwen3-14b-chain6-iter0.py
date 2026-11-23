def score(board, placement):
    lines = placement["lines_cleared"]
    # Compute heights for each column
    heights = []
    for col in range(10):
        current_max = -1
        for row in range(20):
            if board[row][col]:
                current_max = row
        if current_max == -1:
            current_max = 0
        heights.append(current_max)
    max_height = max(heights)
    
    # Compute number of holes
    holes = 0
    for col in range(10):
        has_filled = False
        for row in range(20):
            if board[row][col]:
                has_filled = True
            elif has_filled:
                holes += 1
    
    # Compute roughness (sum of absolute differences between adjacent columns)
    roughness = 0
    for i in range(9):
        roughness += abs(heights[i] - heights[i+1])
    
    # Combine factors into a score
    score_value = (lines * 10) - (max_height * 2) - (holes * 3) - (roughness * 1)
    # Add a small term based on placement parameters to ensure different placements have different scores
    score_value += (placement["column"] + placement["rotation"]) * 0.0001
    
    return float(score_value)
