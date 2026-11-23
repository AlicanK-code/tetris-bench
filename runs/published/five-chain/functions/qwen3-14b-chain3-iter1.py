def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Calculate number of holes
    holes = 0
    for col in range(10):
        filled_above = False
        for row in range(20):
            if board[row][col]:
                filled_above = True
            elif not board[row][col] and filled_above:
                holes += 1
    
    # Calculate heights for each column once
    heights = []
    for col in range(10):
        height = 0
        for row in range(20):
            if board[row][col]:
                height += 1
            else:
                break
        heights.append(height)
    
    max_height = max(heights)
    
    # Calculate surface roughness
    surface_roughness = 0
    for i in range(9):
        surface_roughness += abs(heights[i] - heights[i+1])
    
    # Combine all factors into a score with adjusted weights
    score = (lines_cleared * 1000) - (holes * 50) - (max_height * 20) - (surface_roughness * 10)
    
    # Add small terms to ensure different placements have different scores
    score += placement['rotation'] * 0.01 + placement['column'] * 0.001
    
    return float(score)
