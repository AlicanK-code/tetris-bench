def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    
    # Calculate column heights and holes
    heights = []
    holes = 0
    for col in range(10):
        height = 0
        filled = False
        for row in range(20):
            if board[row][col]:
                height += 1
                filled = True
            else:
                if filled:
                    holes += 1
        heights.append(height)
    
    # Calculate bumpiness
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])
    
    max_height = max(heights)
    
    # Weighted score components
    score = (lines_cleared * 100) - (max_height * 5) - (holes * 10) - (bumpiness * 2)
    
    return float(score)
