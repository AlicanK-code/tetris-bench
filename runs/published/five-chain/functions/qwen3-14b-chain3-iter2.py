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
    sum_squares = sum(h**2 for h in heights)
    
    # Calculate surface roughness
    surface_roughness = 0
    for i in range(9):
        surface_roughness += abs(heights[i] - heights[i+1])
    
    # Combine all factors into a score with adjusted weights
    score = (lines_cleared * 1000) - (holes * 100) - (max_height * 30) - (sum_squares * 5) - (surface_roughness * 20)
    
    # Add small terms to ensure different placements have different scores
    score += placement['rotation'] * 0.01 + placement['column'] * 0.001 + placement['row'] * 0.0001 + ord(placement['kind']) * 0.00001
    
    return float(score)
