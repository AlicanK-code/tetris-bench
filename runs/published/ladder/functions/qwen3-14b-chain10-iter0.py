def score(board, placement):
    # Calculate column heights for max_height and roughness
    column_heights = []
    for col in range(10):
        current_height = 0
        for row in range(20):
            if not board[row][col]:
                current_height = row
                break
        else:
            current_height = 20
        column_heights.append(current_height)
    
    # Calculate max_height
    max_height = max(column_heights)
    
    # Calculate roughness
    roughness = 0
    for i in range(9):
        roughness += abs(column_heights[i] - column_heights[i+1])
    
    # Calculate holes
    holes = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col]:
                # Check if there's any filled cell below
                has_filled_below = False
                for r in range(row + 1, 20):
                    if board[r][col]:
                        has_filled_below = True
                        break
                if has_filled_below:
                    holes += 1
    
    # Combine all factors into a score
    score = (placement["lines_cleared"] * 10) - (max_height * 2) - (holes * 5) - (roughness * 1)
    return float(score)
