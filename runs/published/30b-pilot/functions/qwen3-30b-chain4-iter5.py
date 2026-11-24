def score(board, placement):
    lines = placement["lines_cleared"]
    main_score = lines * 500
    
    holes = 0
    for col in range(10):
        has_filled = False
        for row in range(20):
            if board[row][col]:
                has_filled = True
            elif has_filled:
                holes += 1
    
    heights = [20] * 10
    for col in range(10):
        for row in range(20):
            if board[row][col]:
                heights[col] = row
                break
    surface_variation = 0
    for i in range(9):
        surface_variation += abs(heights[i] - heights[i+1])
    
    total_height = 0
    for col in range(10):
        for row in range(20):
            if board[row][col]:
                total_height += row
                break
    
    unique_term = placement["rotation"] * 10 + placement["column"]
    
    return main_score - (holes * 100) - (surface_variation * 50) - (total_height * 10) + unique_term
