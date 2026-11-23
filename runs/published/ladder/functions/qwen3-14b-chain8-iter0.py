def score(board, placement):
    # Compute column heights
    heights = []
    for col in range(10):
        first_empty = 20  # default if all filled
        for row in range(20):
            if not board[row][col]:
                first_empty = row
                break
        heights.append(first_empty)
    max_height = max(heights)
    
    # Count holes
    num_holes = 0
    for row in range(20):
        for col in range(10):
            if not board[row][col]:
                # Check if there's any filled cell below
                has_filled_below = False
                for row_below in range(row + 1, 20):
                    if board[row_below][col]:
                        has_filled_below = True
                        break
                if has_filled_below:
                    num_holes += 1
    
    # Compute surface evenness
    surface_evenness = sum(abs(heights[i] - heights[i + 1]) for i in range(9))
    
    # Calculate the score with weighted terms
    lines_weight = 100
    height_weight = 1
    holes_weight = 1
    evenness_weight = 0.5
    
    total_score = (
        placement["lines_cleared"] * lines_weight
        - max_height * height_weight
        - num_holes * holes_weight
        - surface_evenness * evenness_weight
    )
    
    return total_score
