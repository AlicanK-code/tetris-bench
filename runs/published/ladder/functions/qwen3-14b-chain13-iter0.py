def score(board, placement):
    # Precompute column heights
    column_heights = []
    for col in range(10):
        h = 0
        for row in range(20):
            if not board[row][col]:
                h = row
                break
        else:
            h = 20
        column_heights.append(h)
    
    # Compute max height
    max_h = max(column_heights)
    
    # Compute roughness
    roughness = 0
    for i in range(9):
        roughness += abs(column_heights[i] - column_heights[i+1])
    
    # Compute holes
    holes = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col]:
                # check if there's any filled cell below in this column
                has_filled_below = False
                for r in range(row+1, 20):
                    if board[r][col]:
                        has_filled_below = True
                        break
                if has_filled_below:
                    holes += 1
    
    # Now calculate the score
    lines = placement["lines_cleared"]
    score = (lines * 10) - (max_h * 0.5) - (holes * 1) - (roughness * 0.2)
    return score
