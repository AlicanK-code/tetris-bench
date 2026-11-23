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
    
    # Calculate total height
    total_height = sum(heights)
    
    # Calculate surface roughness
    surface_roughness = 0
    for i in range(9):
        surface_roughness += abs(heights[i] - heights[i+1])
    
    # Combine all factors into a score
    score = (lines_cleared * 100) - (holes * 10) - (total_height * 1) - (surface_roughness * 0.5)
    return float(score)
