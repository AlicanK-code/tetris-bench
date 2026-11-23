def score(board, placement):
    # Compute column heights
    heights = []
    for col in range(10):
        h = 20  # default if all filled
        for row in range(20):
            if not board[row][col]:
                h = row
                break
        heights.append(h)
    max_height = max(heights)
    
    # Compute number of holes
    num_holes = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col]:
                # Check if there's a filled cell below
                has_filled_below = False
                for r_below in range(row + 1, 20):
                    if board[r_below][col]:
                        has_filled_below = True
                        break
                if has_filled_below:
                    num_holes += 1
    
    # Compute surface roughness
    roughness = 0
    for i in range(9):
        roughness += abs(heights[i] - heights[i + 1])
    
    # Get lines cleared from placement
    lines_cleared = placement["lines_cleared"]
    
    # Combine factors into a score
    score_value = (lines_cleared * 100) - (max_height * 10) - (num_holes * 5) - (roughness * 2)
    
    # Add a small term based on placement parameters to ensure uniqueness
    kind = placement["kind"]
    rotation = placement["rotation"]
    column = placement["column"]
    row = placement["row"]
    
    # Map kind to a number
    kind_code = {'I': 0, 'O':1, 'T':2, 'S':3, 'Z':4, 'J':5, 'L':6}.get(kind, 0)
    
    additional = kind_code * 0.001 + rotation * 0.0001 + column * 0.00001 + row * 0.000001
    
    score_value += additional
    
    return float(score_value)
